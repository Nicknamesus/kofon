"""Async SQLAlchemy engine, session factory, and declarative Base.

Phase 0 has no models yet — Phase 1 adds them and they'll be picked up
automatically via the `Base.metadata` that Alembic reads.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base. Phase 1 models will inherit from this."""


_settings = get_settings()

engine = create_async_engine(
    _settings.effective_database_url,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async session."""
    async with SessionLocal() as session:
        yield session
