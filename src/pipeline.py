"""Scheduler wrapper around the ingestion cycle.

The pipeline service keeps local polling simple: it runs the ingestion cycle on
an interval, avoids overlapping runs, and exposes a small CLI for manual runs
and recent-run inspection.
"""

from __future__ import annotations

import argparse
import logging
import threading

from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import settings
from src.ingest import execute_ingestion_cycle
from src.logging_config import configure_logging
from src.queries import get_recent_ingestion_runs


logger = logging.getLogger(__name__)


class PipelineService:
    """Small runtime wrapper that prevents concurrent ingestion cycles."""

    def __init__(self) -> None:
        self._run_lock = threading.Lock()

    def run_cycle_if_available(self, *, trigger_mode: str, scheduler_job_id: str | None = None):
        """Skip the run if one is already active in this process."""
        if not self._run_lock.acquire(blocking=False):
            logger.warning(
                "Skipping ingestion cycle because another run is still active.",
                extra={"context": {"trigger_mode": trigger_mode}},
            )
            return None

        try:
            return execute_ingestion_cycle(
                trigger_mode=trigger_mode,
                scheduler_job_id=scheduler_job_id,
            )
        finally:
            self._run_lock.release()

    def serve(self) -> None:
        """Run the blocking scheduler for the polling-style local pipeline."""
        scheduler = BlockingScheduler()
        scheduler.add_job(
            self.run_cycle_if_available,
            "interval",
            seconds=settings.pipeline_interval_seconds,
            id="polymarket-ingestion",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=settings.pipeline_misfire_grace_seconds,
            kwargs={"trigger_mode": "scheduled", "scheduler_job_id": "polymarket-ingestion"},
        )
        logger.info(
            "Starting scheduled pipeline service.",
            extra={
                "context": {
                    "interval_seconds": settings.pipeline_interval_seconds,
                    "misfire_grace_seconds": settings.pipeline_misfire_grace_seconds,
                }
            },
        )
        try:
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Pipeline shutdown requested.")
            scheduler.shutdown(wait=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Information Edge automated ingestion pipeline.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = False

    subparsers.add_parser("once")
    subparsers.add_parser("serve")

    runs_parser = subparsers.add_parser("runs")
    runs_parser.add_argument("--limit", type=int, default=10)
    return parser


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or ("serve" if settings.pipeline_continuous_default else "once")
    service = PipelineService()

    if command == "once":
        summary = service.run_cycle_if_available(trigger_mode="manual")
        if summary is not None:
            print(summary.to_cli_summary())
            if getattr(summary, "status", None) != "success":
                raise SystemExit(1)
    elif command == "serve":
        service.serve()
    elif command == "runs":
        from src.db import SessionLocal

        with SessionLocal() as session:
            for run in get_recent_ingestion_runs(session, limit=args.limit):
                print(
                    f"{run.id}\t{run.status}\t{run.trigger_mode}\t"
                    f"{run.run_started_at.isoformat()}\t{run.records_fetched}\t"
                    f"{run.snapshots_inserted}\t{run.integrity_errors}"
                )


if __name__ == "__main__":
    main()
