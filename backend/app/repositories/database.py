"""Database engine (PostgreSQL, or SQLite for local development) and session helpers. Only repositories use this module."""
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(
    url: str,
    connect_timeout_s: int = 5,
    statement_timeout_ms: int = 5_000,
    pool_size: int = 5,
) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"timeout": connect_timeout_s})
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "connect_timeout": connect_timeout_s,
            "options": f"-c statement_timeout={statement_timeout_ms}",
        },
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def dialect_insert(session: Session, table):
    """INSERT that supports ON CONFLICT on the database this session is connected to."""
    module = sqlite if session.get_bind().dialect.name == "sqlite" else postgresql
    return module.insert(table)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One transaction: commit on success, roll back on any error, always close."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
