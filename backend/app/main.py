"""
Pathlight backend entrypoint (FastAPI).

Gate 2 scope: auth + one CRUD vertical slice (Opportunity). Agent routes, MCP routes,
and the outbox worker are added starting Gate 3/4 — see docs/ARCHITECTURE.md.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db
from app.api.routes import auth, opportunities, documents, profile, ingest, preparation, applications, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connects to MongoDB and registers Document models with Beanie. Tests override
    # this behavior (see tests/conftest.py) so they never touch a real MongoDB.
    await init_db()
    yield


app = FastAPI(title="Pathlight API", version="0.1.0", lifespan=lifespan)

# Gate 8: the Next.js frontend runs on a different origin (localhost:3000 vs this
# service's 8000) — without CORS enabled, every browser-originated request fails at the
# preflight OPTIONS step before it ever reaches a route (found via manual browser
# testing, not pytest — TestClient doesn't enforce CORS, so no existing test caught this).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(opportunities.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(ingest.router)
app.include_router(preparation.router)
app.include_router(applications.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
