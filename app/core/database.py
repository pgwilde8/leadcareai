"""SQLAlchemy engine, session factory, and declarative base (lazy initialization)."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    """Create the engine on first use so importing this module does not connect to the DB."""
    settings = get_settings()
    connect_args: dict = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=not settings.database_url.startswith("sqlite"),
    )


@lru_cache
def get_session_local() -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
