"""
Test fixtures: an isolated in-memory MongoDB (via mongomock-motor) per test, with Beanie
initialized against it instead of a real MongoDB connection. Mirrors the role
sqlite:///:memory: + StaticPool played before the Postgres -> MongoDB switch.

Also isolates the sandboxed document-uploads directory (app/mcp/sandbox.py) to a fresh
temp directory per test — without this, uploaded test files would accumulate for real on
disk under backend/data/uploads across every test run, since disk writes aren't reset the
way the Mongo mock is.
"""
from contextlib import asynccontextmanager

import pytest_asyncio
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.core.db import init_db
from app.main import app
import app.mcp.sandbox as sandbox_module


@pytest_asyncio.fixture
async def client(tmp_path):
    # A fresh mock client per test = a fresh empty database per test (test isolation),
    # same guarantee Base.metadata.drop_all() gave us on the SQLite side before.
    mock_client = AsyncMongoMockClient()
    await init_db(client=mock_client)

    # Redirect the sandbox's upload root to a per-test temp directory. sandbox.py's
    # functions read the module-level UPLOADS_ROOT at call time, so reassigning it here
    # takes effect for every upload/read during this test without touching real disk data.
    original_uploads_root = sandbox_module.UPLOADS_ROOT
    sandbox_module.UPLOADS_ROOT = tmp_path

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
