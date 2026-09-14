"""
Pathlight backend entrypoint (FastAPI).

Gate 2 scope: auth + one CRUD vertical slice (Opportunity). Agent routes, MCP routes,
and the outbox worker are added starting Gate 3/4 — see docs/ARCHITECTURE.md.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.db import init_db
from app.api.routes import auth, opportunities, documents, profile, ingest, preparation


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connects to MongoDB and registers Document models with Beanie. Tests override
    # this behavior (see tests/conftest.py) so they never touch a real MongoDB.
    await init_db()
    yield


app = FastAPI(title="Pathlight API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(opportunities.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(ingest.router)
app.include_router(preparation.router)


@app.get("/health")
def health():
    return {"status": "ok"}
