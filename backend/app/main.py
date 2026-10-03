"""
Pathlight backend entrypoint (FastAPI).

Gate 2 scope: auth + one CRUD vertical slice (Opportunity). Agent routes, MCP routes,
and the outbox worker are added starting Gate 3/4 — see docs/ARCHITECTURE.md.
"""
import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import check_production_settings, settings
from app.core.db import init_db
from app.api.routes import account, admin, auth, inbound, opportunities, documents, profile, ingest, preparation, applications, dashboard, integrations, jobs
from app.workers.gmail_poll import run_poll_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connects to MongoDB and registers Document models with Beanie. Tests override
    # this behavior (see tests/conftest.py) so they never touch a real MongoDB.
    if settings.ENVIRONMENT == "production":
        problems = check_production_settings(settings)
        if problems:
            # Fail the deploy loudly rather than serve real users with a guessable JWT
            # secret or a localhost database.
            raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    await init_db()

    # Gate 10: Gmail job-alert poller, in-process (docs/AUTONOMOUS_APPLICATIONS.md §5).
    # Only started when OAuth is actually configured — otherwise no user can have a
    # Gmail integration and the loop would just spin.
    # The daily worker loop: Gmail alerts (when OAuth is configured) + Autopilot.
    poll_task = None
    if settings.GMAIL_POLL_ENABLED:
        poll_task = asyncio.create_task(run_poll_loop())
    try:
        yield
    finally:
        if poll_task is not None:
            poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poll_task


app = FastAPI(title="Pathlight API", version="0.1.0", lifespan=lifespan)

# Gate 8: the Next.js frontend runs on a different origin (localhost:3000 vs this
# service's 8000) — without CORS enabled, every browser-originated request fails at the
# preflight OPTIONS step before it ever reaches a route (found via manual browser
# testing, not pytest — TestClient doesn't enforce CORS, so no existing test caught this).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Cross-origin JS can only read this header if it's exposed — without it, downloads
    # (tailored resume PDF, data export) fall back to a generic filename in production.
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(opportunities.router)
app.include_router(documents.router)
app.include_router(profile.router)
app.include_router(ingest.router)
app.include_router(preparation.router)
app.include_router(applications.router)
app.include_router(dashboard.router)
app.include_router(integrations.router)
app.include_router(integrations.internal_router)
app.include_router(jobs.router)
app.include_router(account.router)
app.include_router(admin.router)
app.include_router(inbound.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    # This service is the API only. People who open its URL in a browser (common right
    # after deploying) get sent to the actual app instead of a bare 404.
    return RedirectResponse(settings.FRONTEND_URL)
