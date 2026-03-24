from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

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


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value


def _get_decimal(name: str, default: str) -> Decimal:
    value = os.getenv(name)
    if value is None:
        value = default
    return Decimal(value)


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
    polymarket_trades_base_url: str = os.getenv(
        "POLYMARKET_TRADES_BASE_URL", "https://data-api.polymarket.com"
    ).rstrip("/")
    polymarket_trades_path: str = os.getenv("POLYMARKET_TRADES_PATH", "/trades")
    polymarket_active: bool = _get_bool("POLYMARKET_ACTIVE", True)
    polymarket_closed: bool = _get_bool("POLYMARKET_CLOSED", False)
    polymarket_limit: int = _get_int("POLYMARKET_LIMIT", 50)
    polymarket_trades_limit: int = _get_int("POLYMARKET_TRADES_LIMIT", 500)
    polymarket_trades_batch_size: int = _get_int("POLYMARKET_TRADES_BATCH_SIZE", 25)
    polymarket_timeout_seconds: int = _get_int("POLYMARKET_TIMEOUT_SECONDS", 15)
    pipeline_interval_seconds: int = _get_int("PIPELINE_INTERVAL_SECONDS", 300)
    pipeline_log_level: str = _get_str("PIPELINE_LOG_LEVEL", "INFO").upper()
    pipeline_log_to_file: bool = _get_bool("PIPELINE_LOG_TO_FILE", False)
    pipeline_log_file: str = _get_str("PIPELINE_LOG_FILE", "logs/pipeline.log")
    pipeline_max_retries: int = _get_int("PIPELINE_MAX_RETRIES", 2)
    pipeline_misfire_grace_seconds: int = _get_int(
        "PIPELINE_MISFIRE_GRACE_SECONDS", 30
    )
    pipeline_continuous_default: bool = _get_bool("PIPELINE_CONTINUOUS_DEFAULT", False)
    signal_price_threshold: Decimal = _get_decimal("SIGNAL_PRICE_THRESHOLD", "0.10")
    signal_volume_multiplier: Decimal = _get_decimal("SIGNAL_VOLUME_MULTIPLIER", "3.0")
    signal_liquidity_threshold: Decimal = _get_decimal("SIGNAL_LIQUIDITY_THRESHOLD", "0.20")
    signal_lookback_window_minutes: int = _get_int("SIGNAL_LOOKBACK_WINDOW_MINUTES", 30)
    whale_min_history_count: int = _get_int("WHALE_MIN_HISTORY_COUNT", 20)
    whale_baseline_trade_count: int = _get_int("WHALE_BASELINE_TRADE_COUNT", 100)
    whale_zscore_threshold: Decimal = _get_decimal("WHALE_ZSCORE_THRESHOLD", "3.0")
    whale_median_multiplier_threshold: Decimal = _get_decimal(
        "WHALE_MEDIAN_MULTIPLIER_THRESHOLD", "5.0"
    )
    whale_absolute_min_notional: Decimal = _get_decimal(
        "WHALE_ABSOLUTE_MIN_NOTIONAL", "250"
    )
    gnews_api_key: str = _get_str("GNEWS_API_KEY", "")
    gnews_base_url: str = _get_str("GNEWS_BASE_URL", "https://gnews.io/api/v4").rstrip("/")
    gnews_search_path: str = _get_str("GNEWS_SEARCH_PATH", "/search")
    sentiment_ttl_hours: int = _get_int("SENTIMENT_TTL_HOURS", 4)
    sentiment_max_docs_per_market: int = _get_int("SENTIMENT_MAX_DOCS_PER_MARKET", 10)
    sentiment_model_name: str = _get_str(
        "SENTIMENT_MODEL_NAME", "cardiffnlp/twitter-roberta-base-sentiment-latest"
    )
    sentiment_request_timeout_seconds: int = _get_int(
        "SENTIMENT_REQUEST_TIMEOUT_SECONDS", 15
    )
    api_cors_origins: str = _get_str(
        "API_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    )

    @property
    def polymarket_events_url(self) -> str:
        return f"{self.polymarket_base_url}{self.polymarket_events_path}"

    @property
    def polymarket_trades_url(self) -> str:
        return f"{self.polymarket_trades_base_url}{self.polymarket_trades_path}"

    @property
    def gnews_search_url(self) -> str:
        return f"{self.gnews_base_url}{self.gnews_search_path}"

    @property
    def api_cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


settings = Settings()
