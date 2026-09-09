"""Database connection helpers (Milestone 4).

SRP: this module only builds engines and session factories. Table
definitions live in `db_models`; CRUD lives in `store`.

Database-agnostic: no SQLite/Postgres-specific code paths except the
connection args SQLAlchemy itself requires per dialect. Point
`DATABASE_URL` at any SQLAlchemy-supported URL (e.g. SQLite file,
`sqlite:///:memory:` for tests, or Postgres
`postgresql+psycopg://user:pass@host/db`) without code changes.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def is_memory_sqlite(url: str) -> bool:
    return url == "sqlite:///:memory:"


def create_engine_for_url(url: str):
    """Build an engine for any SQLAlchemy URL.

    SQLite needs `check_same_thread=False` (FastAPI serves requests on
    multiple threads). In-memory SQLite additionally needs `StaticPool`
    so every session shares the single backing connection — otherwise
    each session would see an empty database.
    """
    kwargs: dict = {}
    if url.startswith("sqlite:"):
        kwargs["connect_args"] = {"check_same_thread": False}
    if is_memory_sqlite(url):
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def create_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(engine) -> None:
    """Create tables from ORM metadata (no-op when they exist).

    Callers must import `db_models` first so all tables are registered
    on `Base.metadata`.
    """
    Base.metadata.create_all(engine)
