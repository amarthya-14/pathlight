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


async def init_db(client=None) -> None:
    """
    Initializes Beanie against a Mongo client.

    Pass `client` explicitly in tests to use an in-memory mongomock-motor client instead
    of connecting to a real MongoDB — this plays the same role `sqlite:///:memory:` +
    StaticPool played before the Postgres -> MongoDB switch (see ARCHITECTURE.md §10).
    """
    mongo_client = client or AsyncIOMotorClient(settings.MONGO_URI)
    await init_beanie(
        database=mongo_client[settings.MONGO_DB_NAME],
        document_models=[User, Profile, Company, Opportunity, Document, Application, AgentExecution],
    )
