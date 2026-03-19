from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base


@pytest.fixture()
def session_factory() -> sessionmaker:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def session(session_factory: sessionmaker) -> Generator[Session, None, None]:
    SessionLocal = session_factory
    with SessionLocal() as db_session:
        yield db_session
