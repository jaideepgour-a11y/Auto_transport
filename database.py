"""
Database initialisation using SQLAlchemy async + aiosqlite.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.load import Load          # noqa: F401  — registers table
from app.models.message_log import MessageLog  # noqa: F401

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
