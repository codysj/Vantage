from __future__ import annotations

from decimal import Decimal

from src.integrity import run_post_write_checks, validate_market_bundle
from src.models import Event, Market
from src.normalize import normalize_event, parse_datetime
from tests.test_normalize import sample_event_payload


def test_validate_market_bundle_flags_invalid_numeric_and_probability() -> None:
    payload = sample_event_payload()
    payload["markets"][0]["volume"] = "not-a-number"
    payload["markets"][0]["outcomePrices"] = "[\"1.2\", \"-0.2\"]"
    normalized = normalize_event(payload, parse_datetime("2026-03-18T00:00:00Z"))

    issues = validate_market_bundle(normalized["markets"][0])

    assert any("invalid numeric field volume" in issue for issue in issues)
    assert any("out-of-range outcome price" in issue for issue in issues)


def test_validate_market_bundle_flags_negative_values() -> None:
    payload = sample_event_payload()
    payload["markets"][0]["liquidity"] = "-5"
    normalized = normalize_event(payload, parse_datetime("2026-03-18T00:00:00Z"))

    issues = validate_market_bundle(normalized["markets"][0])

    assert any("negative liquidity" in issue for issue in issues)


def test_post_write_checks_detect_orphan_markets(session) -> None:
    event = Event(event_id="event-1", title="Event")
    session.add(event)
    session.flush()
    orphan_market = Market(market_id="orphan-1", event_id=9999, question="Bad market")
    session.add(orphan_market)
    session.commit()

    issues = run_post_write_checks(session, records_fetched=1, events_upserted=1)

    assert any("Orphan markets found" in issue for issue in issues)
