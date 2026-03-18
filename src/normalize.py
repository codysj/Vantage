from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from dateutil import parser


logger = logging.getLogger(__name__)


def get_first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        logger.warning("Skipping invalid numeric value: %r", value)
        return None


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    try:
        parsed = parser.isoparse(str(value))
    except (TypeError, ValueError):
        logger.warning("Skipping invalid datetime value: %r", value)
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed JSON string: %r", value)
            return None
    return value


def parse_string_list(value: Any) -> list[str]:
    parsed = parse_jsonish(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return [str(item) for item in parsed if item is not None]
    return [str(parsed)]


def parse_decimal_list(value: Any) -> list[Decimal]:
    parsed = parse_jsonish(value)
    if parsed is None:
        return []
    if not isinstance(parsed, list):
        parsed = [parsed]
    results: list[Decimal] = []
    for item in parsed:
        decimal_value = parse_decimal(item)
        if decimal_value is not None:
            results.append(decimal_value)
    return results


def slugify(value: str) -> str:
    return "-".join(value.strip().lower().split())


def normalize_tag(tag_payload: Any) -> dict[str, Any] | None:
    if tag_payload is None:
        return None
    if isinstance(tag_payload, str):
        label = tag_payload.strip()
        if not label:
            return None
        return {
            "tag_key": slugify(label),
            "external_tag_id": None,
            "label": label,
            "slug": slugify(label),
            "raw_json": {"label": label},
        }
    if not isinstance(tag_payload, dict):
        return None

    label = get_first(tag_payload, "label", "name", "slug")
    if not label:
        return None
    external_id = get_first(tag_payload, "id", "tagId")
    slug = get_first(tag_payload, "slug")
    tag_key = str(external_id) if external_id is not None else slugify(str(label))
    return {
        "tag_key": tag_key,
        "external_tag_id": str(external_id) if external_id is not None else None,
        "label": str(label),
        "slug": slug,
        "raw_json": tag_payload,
    }


def normalize_event_tags(event_payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_tags = get_first(event_payload, "tags", "eventTags")
    parsed = parse_jsonish(raw_tags)
    if parsed is None:
        return []
    if not isinstance(parsed, list):
        parsed = [parsed]
    tags: list[dict[str, Any]] = []
    for item in parsed:
        normalized = normalize_tag(item)
        if normalized is not None:
            tags.append(normalized)
    return tags


def choose_market_type(market_payload: dict[str, Any]) -> str | None:
    market_type = get_first(market_payload, "marketType", "type")
    if market_type is not None:
        return str(market_type)
    outcomes = parse_string_list(get_first(market_payload, "outcomes"))
    if len(outcomes) == 2:
        return "binary"
    return None


def build_snapshot_key(
    market_api_id: str, source_updated_at: datetime | None, dynamic_fields: dict[str, Any]
) -> str:
    if source_updated_at is not None:
        return f"{market_api_id}:{source_updated_at.isoformat()}"
    stable_json = json.dumps(dynamic_fields, sort_keys=True, default=str)
    digest = hashlib.sha256(stable_json.encode("utf-8")).hexdigest()
    return f"{market_api_id}:hash:{digest}"


def normalize_event(event_payload: dict[str, Any], observed_at: datetime) -> dict[str, Any]:
    raw_event_id = get_first(event_payload, "id", "eventId")
    if raw_event_id in (None, ""):
        raise ValueError("Event payload is missing an id/eventId.")
    event_api_id = str(raw_event_id)

    markets_payload = get_first(event_payload, "markets") or []
    if not isinstance(markets_payload, list):
        markets_payload = []

    tags = normalize_event_tags(event_payload)
    normalized_markets = [
        normalize_market(market_payload, event_api_id=event_api_id, observed_at=observed_at)
        for market_payload in markets_payload
        if isinstance(market_payload, dict)
    ]

    return {
        "event": {
            "event_id": event_api_id,
            "slug": get_first(event_payload, "slug"),
            "ticker": get_first(event_payload, "ticker"),
            "title": get_first(event_payload, "title"),
            "description": get_first(event_payload, "description"),
            "question": get_first(event_payload, "question"),
            "category": get_first(event_payload, "category"),
            "active": parse_bool(get_first(event_payload, "active")),
            "closed": parse_bool(get_first(event_payload, "closed")),
            "archived": parse_bool(get_first(event_payload, "archived")),
            "featured": parse_bool(get_first(event_payload, "featured")),
            "restricted": parse_bool(get_first(event_payload, "restricted")),
            "created_at_api": parse_datetime(get_first(event_payload, "createdAt", "created_at")),
            "updated_at_api": parse_datetime(get_first(event_payload, "updatedAt", "updated_at")),
            "start_date": parse_datetime(get_first(event_payload, "startDate", "start_date")),
            "end_date": parse_datetime(get_first(event_payload, "endDate", "end_date")),
            "raw_json": event_payload,
        },
        "markets": normalized_markets,
        "tags": tags,
    }


def normalize_market(
    market_payload: dict[str, Any], *, event_api_id: str, observed_at: datetime
) -> dict[str, Any]:
    raw_market_id = get_first(market_payload, "id", "marketId")
    if raw_market_id in (None, ""):
        raise ValueError(f"Market payload for event {event_api_id} is missing an id/marketId.")
    market_api_id = str(raw_market_id)

    outcomes = parse_string_list(get_first(market_payload, "outcomes"))
    outcome_prices = parse_decimal_list(get_first(market_payload, "outcomePrices"))
    clob_token_ids = parse_string_list(get_first(market_payload, "clobTokenIds"))
    resolution_statuses = parse_string_list(get_first(market_payload, "umaResolutionStatuses"))

    normalized_outcomes: list[dict[str, Any]] = []
    for index, label in enumerate(outcomes):
        normalized_outcomes.append(
            {
                "outcome_index": index,
                "outcome_label": label,
                "current_price": outcome_prices[index] if index < len(outcome_prices) else None,
                "clob_token_id": clob_token_ids[index] if index < len(clob_token_ids) else None,
                "uma_resolution_status": (
                    resolution_statuses[index] if index < len(resolution_statuses) else None
                ),
            }
        )

    source_updated_at = parse_datetime(get_first(market_payload, "updatedAt", "updated_at"))
    dynamic_fields = {
        "last_trade_price": parse_decimal(get_first(market_payload, "lastTradePrice", "last_trade_price")),
        "best_bid": parse_decimal(get_first(market_payload, "bestBid", "best_bid")),
        "best_ask": parse_decimal(get_first(market_payload, "bestAsk", "best_ask")),
        "spread": parse_decimal(get_first(market_payload, "spread")),
        "volume": parse_decimal(get_first(market_payload, "volume")),
        "volume_24hr": parse_decimal(get_first(market_payload, "volume24hr", "volume24Hr")),
        "volume_1wk": parse_decimal(get_first(market_payload, "volume1wk", "volume1Wk")),
        "volume_1mo": parse_decimal(get_first(market_payload, "volume1mo", "volume1Mo")),
        "volume_1yr": parse_decimal(get_first(market_payload, "volume1yr", "volume1Yr")),
        "liquidity": parse_decimal(get_first(market_payload, "liquidity")),
        "liquidity_clob": parse_decimal(get_first(market_payload, "liquidityClob")),
        "volume_clob": parse_decimal(get_first(market_payload, "volumeClob")),
        "open_interest": parse_decimal(get_first(market_payload, "openInterest")),
        "one_day_price_change": parse_decimal(
            get_first(market_payload, "oneDayPriceChange", "priceChange24hr")
        ),
        "one_week_price_change": parse_decimal(get_first(market_payload, "oneWeekPriceChange")),
        "one_month_price_change": parse_decimal(get_first(market_payload, "oneMonthPriceChange")),
        "one_year_price_change": parse_decimal(get_first(market_payload, "oneYearPriceChange")),
        "outcome_prices": [str(value) for value in outcome_prices],
    }

    return {
        "market": {
            "market_id": market_api_id,
            "event_api_id": event_api_id,
            "condition_id": get_first(market_payload, "conditionId"),
            "question_id": get_first(market_payload, "questionId"),
            "slug": get_first(market_payload, "slug"),
            "question": get_first(market_payload, "question", "title"),
            "description": get_first(market_payload, "description"),
            "resolution_source": get_first(market_payload, "resolutionSource"),
            "market_type": choose_market_type(market_payload),
            "active": parse_bool(get_first(market_payload, "active")),
            "closed": parse_bool(get_first(market_payload, "closed")),
            "archived": parse_bool(get_first(market_payload, "archived")),
            "restricted": parse_bool(get_first(market_payload, "restricted")),
            "accepting_orders": parse_bool(get_first(market_payload, "acceptingOrders")),
            "enable_order_book": parse_bool(get_first(market_payload, "enableOrderBook")),
            "order_min_size": parse_decimal(get_first(market_payload, "orderMinSize")),
            "order_price_min_tick_size": parse_decimal(
                get_first(market_payload, "orderPriceMinTickSize")
            ),
            "group_item_title": get_first(market_payload, "groupItemTitle"),
            "group_item_threshold": parse_decimal(get_first(market_payload, "groupItemThreshold")),
            "created_at_api": parse_datetime(get_first(market_payload, "createdAt", "created_at")),
            "updated_at_api": source_updated_at,
            "start_date": parse_datetime(get_first(market_payload, "startDate", "start_date")),
            "end_date": parse_datetime(get_first(market_payload, "endDate", "end_date")),
            "start_date_iso": parse_datetime(get_first(market_payload, "startDateIso")),
            "end_date_iso": parse_datetime(get_first(market_payload, "endDateIso")),
            "raw_json": market_payload,
        },
        "outcomes": normalized_outcomes,
        "snapshot": {
            "observed_at": observed_at,
            "source_updated_at": source_updated_at,
            "snapshot_key": build_snapshot_key(market_api_id, source_updated_at, dynamic_fields),
            **dynamic_fields,
            "raw_json": market_payload,
        },
    }
