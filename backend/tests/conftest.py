"""
Test fixtures: an isolated in-memory MongoDB (via mongomock-motor) per test, with Beanie
initialized against it instead of a real MongoDB connection. Mirrors the role
sqlite:///:memory: + StaticPool played before the Postgres -> MongoDB switch.

Also isolates the sandboxed document-uploads directory (app/mcp/sandbox.py) and the
Chroma vector store directory (app/retrieval/vector_store.py) to fresh temp directories
per test — without this, test data would accumulate for real on disk across every test
run, since disk writes aren't reset the way the Mongo mock is.

Every test gets a FAKE embedder (tests/fakes.py) by default, not just tests that opt in.
This is necessary, not optional: document upload/paste routes index resumes into Chroma
automatically (see app/api/routes/documents.py), so ANY test that uploads a resume —
including tests written before Gate 5 existed — would otherwise try to call the real
Gemini embedding API and fail (this sandbox cannot reach it; see
app/retrieval/embeddings.py). Tests that specifically exercise embedding-distance
behavior (tests/test_skill_gap_agent.py) rely on this same default fake rather than
patching their own, so its vectors are documented once, here.
"""
from contextlib import asynccontextmanager

import pytest_asyncio
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.core.db import init_db
from app.main import app
import app.mcp.sandbox as sandbox_module
import app.retrieval.vector_store as vector_store_module
from app.core.config import settings as app_settings
from tests.fakes import FakeEmbedder


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    # A fresh mock client per test = a fresh empty database per test (test isolation),
    # same guarantee Base.metadata.drop_all() gave us on the SQLite side before.
    mock_client = AsyncMongoMockClient()
    await init_db(client=mock_client)

    # Redirect the sandbox's upload root to a per-test temp directory. sandbox.py's
    # functions read the module-level UPLOADS_ROOT at call time, so reassigning it here
    # takes effect for every upload/read during this test without touching real disk data.
    original_uploads_root = sandbox_module.UPLOADS_ROOT
    sandbox_module.UPLOADS_ROOT = tmp_path

    # Redirect Chroma's persistence directory the same way, and reset its cached client
    # singleton so a fresh PersistentClient is created against the new (empty) directory
    # instead of reusing one already pointed at a previous test's data.
    original_chroma_dir = app_settings.CHROMA_PERSIST_DIR
    app_settings.CHROMA_PERSIST_DIR = str(tmp_path / "chroma")
    vector_store_module._client = None

    # Default fake embedder for every test — see module docstring above for why this
    # can't be opt-in only.
    fake_embedder = FakeEmbedder()
    monkeypatch.setattr("app.retrieval.vector_store.get_document_embedder", lambda: fake_embedder)
    monkeypatch.setattr("app.retrieval.vector_store.get_query_embedder", lambda: fake_embedder)

    @asynccontextmanager
    async def noop_lifespan(app):
        # Beanie is already initialized above against the mock client; skip the app's
        # own lifespan so it doesn't try to reach a real MongoDB.
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.router.lifespan_context = original_lifespan
        sandbox_module.UPLOADS_ROOT = original_uploads_root
        app_settings.CHROMA_PERSIST_DIR = original_chroma_dir
        vector_store_module._client = None
