from __future__ import annotations

from typing import Any

from sqlalchemy.orm import sessionmaker

from src.models import IngestionRun


def create_run(
    session_factory: sessionmaker,
    *,
    trigger_mode: str,
    run_started_at,
    scheduler_job_id: str | None = None,
    api_source: str = "gamma_events",
) -> IngestionRun:
    with session_factory() as session:
        run = IngestionRun(
            run_started_at=run_started_at,
            status="running",
            trigger_mode=trigger_mode,
            scheduler_job_id=scheduler_job_id,
            api_source=api_source,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


def update_run(session_factory: sessionmaker, run_id: int, **fields: Any) -> None:
    with session_factory() as session:
        run = session.get(IngestionRun, run_id)
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)
        session.commit()
