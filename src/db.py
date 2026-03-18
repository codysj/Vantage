from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings
from src.models import Base


def create_db_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or settings.database_url, future=True)


engine = create_db_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session(database_url: str | None = None) -> Session:
    if database_url is None:
        return SessionLocal()
    return sessionmaker(
        bind=create_db_engine(database_url),
        autoflush=False,
        autocommit=False,
        future=True,
    )()


def init_db(database_url: str | None = None) -> None:
    db_engine = engine if database_url is None else create_db_engine(database_url)
    Base.metadata.create_all(db_engine)
