from __future__ import annotations

import logging
from pathlib import Path

from src.config import settings


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context = getattr(record, "context", None) or {}
        if not context:
            return base
        parts = [f"{key}={value}" for key, value in sorted(context.items())]
        return f"{base} | {' '.join(parts)}"


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.pipeline_log_level, logging.INFO))
    root_logger.handlers.clear()

    formatter = KeyValueFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if settings.pipeline_log_to_file:
        log_path = Path(settings.pipeline_log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
