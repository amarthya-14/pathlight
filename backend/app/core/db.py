"""
MongoDB connection + Beanie ODM initialization.

Beanie Documents declare their own schema and indexes (see app/models/) — there's no
SQL-style migration step; collections and indexes are created/ensured the first time
init_db() runs against a given database.
"""
from motor.motor_asyncio import AsyncIOMotorClient

from beanie import init_beanie

from app.core.config import settings
from app.models.user import User, Profile
from app.models.opportunity import Company, Opportunity
from app.models.document import Document
from app.models.application import Application
from app.models.agent_execution import AgentExecution
from app.models.preparation import PreparationPlan
from app.models.calendar_event import CalendarEvent
from app.models.integration import Integration
from app.models.tailored_resume import TailoredResume
from app.models.job_listing import JobListing
from app.core.usage import UsageCounter
from app.models.inbound import AlertAddress, InboundEmail


async def init_db(client=None) -> None:
    """
    Initializes Beanie against a Mongo client.

    Pass `client` explicitly in tests to use an in-memory mongomock-motor client instead
    of connecting to a real MongoDB — this plays the same role `sqlite:///:memory:` +
    StaticPool played before the Postgres -> MongoDB switch (see ARCHITECTURE.md §10).
    """
    # tz_aware: MongoDB stores UTC but hands back naive datetimes by default, which the API
    # then serialises without a timezone — browsers read those as local (IST) time and
    # every "2h ago" was 5.5 hours off. Aware datetimes serialise with +00:00.
    mongo_client = client or AsyncIOMotorClient(settings.MONGO_URI, tz_aware=True)
    await init_beanie(
        database=mongo_client[settings.MONGO_DB_NAME],
        document_models=[
            User, Profile, Company, Opportunity, Document, Application, AgentExecution,
            PreparationPlan, CalendarEvent, Integration, TailoredResume, JobListing, UsageCounter, AlertAddress, InboundEmail,
        ],
    )
