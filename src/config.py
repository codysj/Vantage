from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/information_edge",
    )
    polymarket_base_url: str = os.getenv(
        "POLYMARKET_BASE_URL", "https://gamma-api.polymarket.com"
    ).rstrip("/")
    polymarket_events_path: str = os.getenv("POLYMARKET_EVENTS_PATH", "/events")
    polymarket_active: bool = _get_bool("POLYMARKET_ACTIVE", True)
    polymarket_closed: bool = _get_bool("POLYMARKET_CLOSED", False)
    polymarket_limit: int = _get_int("POLYMARKET_LIMIT", 50)
    polymarket_timeout_seconds: int = _get_int("POLYMARKET_TIMEOUT_SECONDS", 15)

    @property
    def polymarket_events_url(self) -> str:
        return f"{self.polymarket_base_url}{self.polymarket_events_path}"


settings = Settings()
