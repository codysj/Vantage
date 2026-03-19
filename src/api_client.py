from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import requests

from src.config import settings


class PolymarketClient:
    def __init__(
        self,
        base_url: str | None = None,
        events_path: str | None = None,
        trades_base_url: str | None = None,
        trades_path: str | None = None,
        timeout_seconds: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = (base_url or settings.polymarket_base_url).rstrip("/")
        self.events_path = events_path or settings.polymarket_events_path
        self.trades_base_url = (
            trades_base_url or settings.polymarket_trades_base_url
        ).rstrip("/")
        self.trades_path = trades_path or settings.polymarket_trades_path
        self.timeout_seconds = timeout_seconds or settings.polymarket_timeout_seconds
        self.max_retries = settings.pipeline_max_retries
        self.session = session or requests.Session()

    @property
    def events_url(self) -> str:
        return f"{self.base_url}{self.events_path}"

    @property
    def trades_url(self) -> str:
        return f"{self.trades_base_url}{self.trades_path}"

    def _get_json_with_retries(
        self,
        url: str,
        *,
        params: dict[str, Any],
        expected_type: type,
        error_message: str,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_seconds)
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(
                        f"Transient API status {response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, expected_type):
                    raise ValueError(error_message)
                return payload
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                if attempt > self.max_retries:
                    break
                time.sleep(attempt)
        if last_error is None:
            raise RuntimeError("Polymarket fetch failed without a recorded exception.")
        raise last_error

    def fetch_events(
        self, *, active: bool | None = None, closed: bool | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        params = {
            "active": str(settings.polymarket_active if active is None else active).lower(),
            "closed": str(settings.polymarket_closed if closed is None else closed).lower(),
            "limit": settings.polymarket_limit if limit is None else limit,
        }
        return self._get_json_with_retries(
            self.events_url,
            params=params,
            expected_type=list,
            error_message="Expected Polymarket /events response to be a list.",
        )

    def fetch_trades(
        self,
        *,
        condition_ids: Sequence[str],
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not condition_ids:
            return []
        params = {
            "market": ",".join(condition_ids),
            "limit": settings.polymarket_trades_limit if limit is None else limit,
            "offset": offset,
        }
        return self._get_json_with_retries(
            self.trades_url,
            params=params,
            expected_type=list,
            error_message="Expected Polymarket /trades response to be a list.",
        )
