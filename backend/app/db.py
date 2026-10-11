import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./gamesense.db"


def get_database_url() -> str:
    """Return the configured database URL.

    Local one-command runs default to SQLite. Docker Compose and production-like
    deployments should set DATABASE_URL to PostgreSQL or another SQLAlchemy URL.
    """

    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_database_url()
    return create_engine(url, connect_args=_connect_args(url), pool_pre_ping=True, future=True)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def database_is_ready(session: Session) -> bool:
    session.execute(text("SELECT 1"))
    return True
