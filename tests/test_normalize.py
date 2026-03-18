from __future__ import annotations

from decimal import Decimal

from src.normalize import normalize_event, parse_datetime, parse_decimal, parse_decimal_list, parse_string_list


def sample_event_payload() -> dict:
    return {
        "id": "event-1",
        "slug": "fed-rate-cut",
        "title": "Will the Fed cut rates?",
        "description": "Sample event",
        "question": "Will the Fed cut rates in June?",
        "active": True,
        "closed": False,
        "tags": [{"id": 10, "label": "Macro", "slug": "macro"}],
        "createdAt": "2026-03-01T12:00:00Z",
        "markets": [
            {
                "id": "market-1",
                "slug": "will-fed-cut-rates-june",
                "question": "Will the Fed cut rates in June?",
                "outcomes": "[\"Yes\", \"No\"]",
                "outcomePrices": "[\"0.43\", \"0.57\"]",
                "clobTokenIds": "[\"tok-yes\", \"tok-no\"]",
                "umaResolutionStatuses": "[\"pending\", \"pending\"]",
                "volume": "100.5",
                "liquidity": 25,
                "updatedAt": "2026-03-02T15:30:00Z",
            }
        ],
    }


def test_parse_stringified_lists() -> None:
    assert parse_string_list("[\"Yes\", \"No\"]") == ["Yes", "No"]
    assert parse_decimal_list("[\"0.25\", \"0.75\"]") == [Decimal("0.25"), Decimal("0.75")]
    assert parse_string_list("[bad json") == []


def test_numeric_and_timestamp_coercion() -> None:
    assert parse_decimal("12.34") == Decimal("12.34")
    assert parse_decimal(7) == Decimal("7")
    parsed = parse_datetime("2026-03-02T15:30:00Z")
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_normalize_event_builds_market_outcomes_and_snapshot() -> None:
    normalized = normalize_event(sample_event_payload(), parse_datetime("2026-03-18T00:00:00Z"))
    market = normalized["markets"][0]

    assert normalized["event"]["event_id"] == "event-1"
    assert normalized["tags"][0]["tag_key"] == "10"
    assert market["outcomes"][0]["outcome_label"] == "Yes"
    assert market["outcomes"][1]["current_price"] == Decimal("0.57")
    assert market["snapshot"]["volume"] == Decimal("100.5")
    assert market["snapshot"]["snapshot_key"].startswith("market-1:2026-03-02T15:30:00+00:00")
