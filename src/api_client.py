from __future__ import annotations

from typing import Any

import requests

from src.config import settings


class PolymarketClient:
    def __init__(
        self,
        base_url: str | None = None,
        events_path: str | None = None,
        timeout_seconds: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (base_url or settings.polymarket_base_url).rstrip("/")
        self.events_path = events_path or settings.polymarket_events_path
        self.timeout_seconds = timeout_seconds or settings.polymarket_timeout_seconds
        self.session = session or requests.Session()

    @property
    def events_url(self) -> str:
        return f"{self.base_url}{self.events_path}"

    def fetch_events(
        self, *, active: bool | None = None, closed: bool | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        params = {
            "active": str(settings.polymarket_active if active is None else active).lower(),
            "closed": str(settings.polymarket_closed if closed is None else closed).lower(),
            "limit": settings.polymarket_limit if limit is None else limit,
        }
        response = self.session.get(
            self.events_url, params=params, timeout=self.timeout_seconds
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Expected Polymarket /events response to be a list.")
        return payload
