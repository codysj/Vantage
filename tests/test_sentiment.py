from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from src.config import settings
from src.models import MarketSentimentSummary, SentimentDocument, SentimentScore
from src.sentiment import (
    DocumentCandidate,
    SentimentComputationResult,
    SentimentInference,
    SentimentModelError,
    SentimentUpstreamError,
    _confidence_to_value,
    derive_market_query,
    get_or_compute_market_sentiment,
)
from tests.test_whales import seed_market


class StubSentimentService:
    def __init__(self, results: list[SentimentInference]) -> None:
        self.results = results
        self.calls = 0

    def score_texts(self, texts: list[str]) -> list[SentimentInference]:
        self.calls += 1
        return self.results[: len(texts)]


def test_derive_market_query_strips_noise(session) -> None:
    market = seed_market(session)
    market.question = "Will Donald Trump win the 2028 election?"

    query = derive_market_query(market)

    assert query == "Donald Trump win the 2028 election"


def test_sentiment_value_mapping() -> None:
    assert _confidence_to_value("positive", Decimal("0.82")) == Decimal("0.82")
    assert _confidence_to_value("negative", Decimal("0.40")) == Decimal("-0.40")
    assert _confidence_to_value("neutral", Decimal("0.99")) == Decimal("0")


def test_get_or_compute_market_sentiment_cache_miss_dedupes_and_scores(session, monkeypatch) -> None:
    market = seed_market(session)
    service = StubSentimentService(
        [SentimentInference(label="positive", confidence=Decimal("0.80"), sentiment_value=Decimal("0.80"))]
    )

    monkeypatch.setattr(
        "src.sentiment.fetch_documents_for_market",
        lambda query, max_docs: [
            DocumentCandidate(
                source_name="Reuters",
                url="https://example.com/story-1",
                title="Fed outlook in focus",
                snippet="Traders watch the Fed.",
                raw_text="Fed outlook in focus Traders watch the Fed.",
                published_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
            ),
            DocumentCandidate(
                source_name="Reuters",
                url="https://example.com/story-1",
                title="Fed outlook in focus",
                snippet="Traders watch the Fed.",
                raw_text="Fed outlook in focus Traders watch the Fed.",
                published_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
            ),
        ],
    )
    monkeypatch.setattr("src.sentiment.get_sentiment_service", lambda: service)

    result = get_or_compute_market_sentiment(session, market.market_id)

    assert isinstance(result, SentimentComputationResult)
    assert result.from_cache is False
    assert result.summary.doc_count == 1
    assert result.summary.pos_count == 1
    assert service.calls == 1
    assert len(session.execute(select(SentimentDocument)).scalars().all()) == 1


def test_get_or_compute_market_sentiment_cache_hit_skips_fetch_and_model(session, monkeypatch) -> None:
    market = seed_market(session)
    document = SentimentDocument(
        market_id=market.id,
        source_name="Reuters",
        url="https://example.com/story-2",
        title="BTC climbs",
        snippet="Sentiment improves.",
        raw_text="BTC climbs Sentiment improves.",
        published_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
    )
    session.add(document)
    session.flush()
    session.add(
        SentimentScore(
            document_id=document.id,
            model_name=settings.sentiment_model_name,
            sentiment_label="positive",
            sentiment_confidence=Decimal("0.75"),
            sentiment_value=Decimal("0.75"),
            scored_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
        )
    )
    session.add(
        MarketSentimentSummary(
            market_id=market.id,
            avg_sentiment=Decimal("0.75"),
            doc_count=1,
            pos_count=1,
            neg_count=0,
            neutral_count=0,
            last_computed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    def fail_fetch(*_args, **_kwargs):
        raise AssertionError("fetch_documents_for_market should not be called on cache hit")

    def fail_model():
        raise AssertionError("get_sentiment_service should not be called on cache hit")

    monkeypatch.setattr("src.sentiment.fetch_documents_for_market", fail_fetch)
    monkeypatch.setattr("src.sentiment.get_sentiment_service", fail_model)

    result = get_or_compute_market_sentiment(session, market.market_id)

    assert result is not None
    assert result.from_cache is True
    assert result.summary.doc_count == 1


def test_get_or_compute_market_sentiment_stale_cache_refreshes(session, monkeypatch) -> None:
    market = seed_market(session)
    old_summary = MarketSentimentSummary(
        market_id=market.id,
        avg_sentiment=Decimal("0"),
        doc_count=0,
        pos_count=0,
        neg_count=0,
        neutral_count=0,
        last_computed_at=datetime.now(timezone.utc) - timedelta(hours=settings.sentiment_ttl_hours + 1),
    )
    session.add(old_summary)
    session.commit()

    service = StubSentimentService(
        [SentimentInference(label="negative", confidence=Decimal("0.66"), sentiment_value=Decimal("-0.66"))]
    )
    monkeypatch.setattr(
        "src.sentiment.fetch_documents_for_market",
        lambda query, max_docs: [
            DocumentCandidate(
                source_name="AP",
                url="https://example.com/story-3",
                title="Market concern rises",
                snippet="Traders show concern.",
                raw_text="Market concern rises Traders show concern.",
                published_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
            )
        ],
    )
    monkeypatch.setattr("src.sentiment.get_sentiment_service", lambda: service)

    result = get_or_compute_market_sentiment(session, market.market_id)

    assert result is not None
    assert result.from_cache is False
    assert result.summary.neg_count == 1
    assert service.calls == 1


def test_get_or_compute_market_sentiment_empty_documents_creates_zero_summary(session, monkeypatch) -> None:
    market = seed_market(session)

    monkeypatch.setattr("src.sentiment.fetch_documents_for_market", lambda query, max_docs: [])
    monkeypatch.setattr("src.sentiment.get_sentiment_service", lambda: StubSentimentService([]))

    result = get_or_compute_market_sentiment(session, market.market_id)

    assert result is not None
    assert result.summary.doc_count == 0
    assert result.summary.avg_sentiment == Decimal("0")
    assert result.documents == []


def test_get_or_compute_market_sentiment_surfaces_upstream_errors(session, monkeypatch) -> None:
    market = seed_market(session)

    monkeypatch.setattr(
        "src.sentiment.fetch_documents_for_market",
        lambda query, max_docs: (_ for _ in ()).throw(
            SentimentUpstreamError("Headline source is temporarily unavailable.")
        ),
    )

    try:
        get_or_compute_market_sentiment(session, market.market_id)
    except SentimentUpstreamError as exc:
        assert "Headline source" in str(exc)
    else:
        raise AssertionError("Expected SentimentUpstreamError")


def test_get_or_compute_market_sentiment_model_errors_bubble_cleanly(session, monkeypatch) -> None:
    market = seed_market(session)

    monkeypatch.setattr(
        "src.sentiment.fetch_documents_for_market",
        lambda query, max_docs: [
            DocumentCandidate(
                source_name="Reuters",
                url="https://example.com/story-4",
                title="Rates in focus",
                snippet="Markets watch the Fed.",
                raw_text="Rates in focus Markets watch the Fed.",
                published_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
            )
        ],
    )

    class BrokenService:
        def score_texts(self, texts):
            raise SentimentModelError("Sentiment model is temporarily unavailable.")

    monkeypatch.setattr("src.sentiment.get_sentiment_service", lambda: BrokenService())

    try:
        get_or_compute_market_sentiment(session, market.market_id)
    except SentimentModelError as exc:
        assert "Sentiment model" in str(exc)
    else:
        raise AssertionError("Expected SentimentModelError")
