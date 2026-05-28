"""
Database Configuration

Production-grade async SQLAlchemy setup:
- Async PostgreSQL engine
- Connection pooling
- Transaction safety
- Graceful shutdown
- Pool health checking
"""

from __future__ import annotations

from typing import AsyncGenerator

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger()


# ---------------------------------------------------------------------
# SQLAlchemy Base
# ---------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------
# Async Engine
# ---------------------------------------------------------------------

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.DEBUG,
    future=True,

    # Pooling
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,

    # Reliability
    pool_pre_ping=True,

    # Optional production hardening
    connect_args={
        "server_settings": {
            "application_name": settings.PROJECT_NAME,
        }
    },
)


# ---------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    """

    async with async_session_maker() as session:
        try:
            yield session

        except SQLAlchemyError:
            await session.rollback()

            logger.exception("database_transaction_error")

            raise

        except Exception:
            await session.rollback()

            logger.exception("unexpected_database_error")

            raise

        finally:
            await session.close()


# ---------------------------------------------------------------------
# Shutdown Helper
# ---------------------------------------------------------------------

async def close_database() -> None:
    """
    Gracefully dispose database engine.
    """

    logger.info("database_engine_disposing")

    await engine.dispose()

    logger.info("database_engine_disposed")