from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Any

import requests
from dateutil.parser import isoparse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from src.config import settings
from src.db import SessionLocal
from src.models import Market, MarketSentimentSummary, SentimentDocument, SentimentScore
from src.queries import get_market_by_api_id


logger = logging.getLogger(__name__)

POSITIVE_LABELS = {"positive", "pos", "label_2"}
NEGATIVE_LABELS = {"negative", "neg", "label_0"}
NEUTRAL_LABELS = {"neutral", "label_1"}


@dataclass(frozen=True)
class DocumentCandidate:
    source_name: str | None
    url: str
    title: str | None
    snippet: str | None
    raw_text: str
    published_at: datetime | None


@dataclass(frozen=True)
class SentimentInference:
    label: str
    confidence: Decimal
    sentiment_value: Decimal


@dataclass(frozen=True)
class SentimentComputationResult:
    market: Market
    summary: MarketSentimentSummary
    documents: list[tuple[SentimentDocument, SentimentScore | None]]
    from_cache: bool


class SentimentConfigurationError(RuntimeError):
    pass


class SentimentUpstreamError(RuntimeError):
    pass


class SentimentModelError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_label(label: str) -> str:
    normalized = label.strip().lower()
    if normalized in POSITIVE_LABELS:
        return "positive"
    if normalized in NEGATIVE_LABELS:
        return "negative"
    if normalized in NEUTRAL_LABELS:
        return "neutral"
    return normalized


def _confidence_to_value(label: str, confidence: float | Decimal) -> Decimal:
    numeric_confidence = Decimal(str(confidence))
    normalized_label = _normalize_label(label)
    if normalized_label == "positive":
        return numeric_confidence
    if normalized_label == "negative":
        return numeric_confidence * Decimal("-1")
    return Decimal("0")


def _clean_query_text(value: str) -> str:
    cleaned = value.replace("-", " ")
    cleaned = re.sub(r"[^A-Za-z0-9\s$%.-]", " ", cleaned)
    cleaned = re.sub(
        r"^(will|who|what|when|where|is|are|does|do|can|could|should)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(this|that|there|be|happen|happens)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def derive_market_query(market: Market) -> str:
    base = market.question or market.event.title or market.slug or market.market_id
    cleaned = _clean_query_text(base)
    if not cleaned:
        cleaned = market.slug.replace("-", " ") if market.slug else market.market_id
    tokens = cleaned.split()
    if market.event.category and len(tokens) < 4:
        cleaned = f"{cleaned} {market.event.category}".strip()
        tokens = cleaned.split()
    if len(tokens) > 12:
        cleaned = " ".join(tokens[:12])
    return cleaned


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = isoparse(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_documents_for_market(query: str, max_docs: int | None = None) -> list[DocumentCandidate]:
    if not settings.gnews_api_key:
        raise SentimentConfigurationError("GNEWS_API_KEY is required for sentiment fetching.")

    try:
        response = requests.get(
            settings.gnews_search_url,
            params={
                "q": query,
                "apikey": settings.gnews_api_key,
                "max": max_docs or settings.sentiment_max_docs_per_market,
                "lang": "en",
                "sortby": "publishedAt",
            },
            timeout=settings.sentiment_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning("Sentiment upstream request failed for query '%s': %s", query, exc)
        raise SentimentUpstreamError("Headline source is temporarily unavailable.") from exc
    except ValueError as exc:
        logger.warning("Sentiment upstream returned invalid JSON for query '%s': %s", query, exc)
        raise SentimentUpstreamError("Headline source returned malformed data.") from exc

    articles = payload.get("articles", [])
    if not isinstance(articles, list):
        logger.warning("Sentiment upstream returned invalid articles payload for query '%s'", query)
        raise SentimentUpstreamError("Headline source returned malformed data.")

    seen_urls: set[str] = set()
    candidates: list[DocumentCandidate] = []
    for article in articles:
        url = (article.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        title = (article.get("title") or "").strip() or None
        snippet = (article.get("description") or "").strip() or None
        raw_text = " ".join(part for part in [title, snippet] if part).strip()
        if not raw_text:
            continue
        source = article.get("source") or {}
        candidates.append(
            DocumentCandidate(
                source_name=(source.get("name") or "").strip() or None,
                url=url,
                title=title,
                snippet=snippet,
                raw_text=raw_text,
                published_at=_parse_published_at(article.get("publishedAt")),
            )
        )
        seen_urls.add(url)
    return candidates


class HuggingFaceSentimentService:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline
            except ImportError as exc:
                logger.error("Transformers import failed for sentiment model '%s': %s", self.model_name, exc)
                raise SentimentModelError("Sentiment model is temporarily unavailable.") from exc

            try:
                self._pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                    tokenizer=self.model_name,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                logger.error("Sentiment model load failed for '%s': %s", self.model_name, exc)
                raise SentimentModelError("Sentiment model is temporarily unavailable.") from exc
        return self._pipeline

    def score_texts(self, texts: list[str]) -> list[SentimentInference]:
        if not texts:
            return []

        pipeline_instance = self._get_pipeline()
        try:
            outputs = pipeline_instance(texts, batch_size=min(len(texts), 16), truncation=True)
        except Exception as exc:
            logger.error("Sentiment inference failed for %s texts: %s", len(texts), exc)
            raise SentimentModelError("Sentiment model is temporarily unavailable.") from exc
        results: list[SentimentInference] = []
        for output in outputs:
            label = _normalize_label(str(output.get("label", "neutral")))
            confidence = Decimal(str(output.get("score", 0)))
            results.append(
                SentimentInference(
                    label=label,
                    confidence=confidence,
                    sentiment_value=_confidence_to_value(label, confidence),
                )
            )
        return results


@lru_cache(maxsize=1)
def get_sentiment_service() -> HuggingFaceSentimentService:
    return HuggingFaceSentimentService(settings.sentiment_model_name)


def _is_summary_fresh(summary: MarketSentimentSummary | None) -> bool:
    if summary is None:
        return False
    threshold = _utc_now() - timedelta(hours=settings.sentiment_ttl_hours)
    last_computed = summary.last_computed_at
    if last_computed.tzinfo is None:
        last_computed = last_computed.replace(tzinfo=timezone.utc)
    return last_computed >= threshold


def _market_has_current_model_scores(session: Session, market: Market, model_name: str) -> bool:
    score_count = session.execute(
        select(SentimentScore.id)
        .join(SentimentDocument, SentimentScore.document_id == SentimentDocument.id)
        .where(
            SentimentDocument.market_id == market.id,
            SentimentScore.model_name == model_name,
        )
    ).scalars().all()
    return len(score_count) > 0 or not session.execute(
        select(SentimentDocument.id).where(SentimentDocument.market_id == market.id)
    ).scalars().first()


def _reload_market_sentiment(
    session: Session,
    market_id: str,
    model_name: str,
    *,
    from_cache: bool,
) -> SentimentComputationResult | None:
    market = session.execute(
        select(Market)
        .options(joinedload(Market.event))
        .where(Market.market_id == market_id)
    ).unique().scalar_one_or_none()
    if market is None:
        return None

    summary = session.execute(
        select(MarketSentimentSummary).where(MarketSentimentSummary.market_id == market.id)
    ).scalar_one_or_none()
    if summary is None:
        return None

    return SentimentComputationResult(
        market=market,
        summary=summary,
        documents=_get_market_documents(session, market, model_name),
        from_cache=from_cache,
    )


def _get_market_documents(
    session: Session, market: Market, model_name: str
) -> list[tuple[SentimentDocument, SentimentScore | None]]:
    stmt = (
        select(SentimentDocument, SentimentScore)
        .outerjoin(
            SentimentScore,
            (SentimentScore.document_id == SentimentDocument.id)
            & (SentimentScore.model_name == model_name),
        )
        .where(SentimentDocument.market_id == market.id)
        .order_by(SentimentDocument.published_at.desc(), SentimentDocument.fetched_at.desc())
    )
    return list(session.execute(stmt).all())


def _upsert_documents(
    session: Session, market: Market, candidates: list[DocumentCandidate]
) -> list[SentimentDocument]:
    if not candidates:
        return []

    unique_candidates: list[DocumentCandidate] = []
    seen_urls: set[str] = set()
    for candidate in candidates:
        if candidate.url in seen_urls:
            continue
        unique_candidates.append(candidate)
        seen_urls.add(candidate.url)

    existing_by_url = {
        document.url: document
        for document in session.execute(
            select(SentimentDocument).where(
                SentimentDocument.url.in_([candidate.url for candidate in unique_candidates])
            )
        )
        .scalars()
        .all()
    }

    inserted: list[SentimentDocument] = []
    for candidate in unique_candidates:
        if candidate.url in existing_by_url:
            continue
        document = SentimentDocument(
            market_id=market.id,
            source_name=candidate.source_name,
            url=candidate.url,
            title=candidate.title,
            snippet=candidate.snippet,
            raw_text=candidate.raw_text,
            published_at=candidate.published_at,
            fetched_at=_utc_now(),
        )
        session.add(document)
        inserted.append(document)

    if inserted:
        session.flush()
    return inserted


def _score_missing_documents(
    session: Session,
    documents: list[SentimentDocument],
    model_name: str,
) -> int:
    if not documents:
        return 0

    already_scored_ids = {
        document_id
        for document_id in session.execute(
            select(SentimentScore.document_id).where(
                SentimentScore.document_id.in_([document.id for document in documents]),
                SentimentScore.model_name == model_name,
            )
        )
        .scalars()
        .all()
    }

    documents_to_score = [document for document in documents if document.id not in already_scored_ids]
    if not documents_to_score:
        return 0

    service = get_sentiment_service()
    inferences = service.score_texts([document.raw_text or "" for document in documents_to_score])
    for document, inference in zip(documents_to_score, inferences, strict=True):
        session.add(
            SentimentScore(
                document_id=document.id,
                model_name=model_name,
                sentiment_label=inference.label,
                sentiment_confidence=inference.confidence,
                sentiment_value=inference.sentiment_value,
                scored_at=_utc_now(),
            )
        )
    session.flush()
    return len(documents_to_score)


def _recompute_summary(session: Session, market: Market, model_name: str) -> MarketSentimentSummary:
    rows = _get_market_documents(session, market, model_name)
    scores = [score for _document, score in rows if score is not None]
    doc_count = len(scores)
    pos_count = sum(1 for score in scores if score.sentiment_label == "positive")
    neg_count = sum(1 for score in scores if score.sentiment_label == "negative")
    neutral_count = sum(1 for score in scores if score.sentiment_label == "neutral")
    avg_sentiment = (
        sum((score.sentiment_value for score in scores), Decimal("0")) / Decimal(doc_count)
        if doc_count
        else Decimal("0")
    )

    summary = session.execute(
        select(MarketSentimentSummary).where(MarketSentimentSummary.market_id == market.id)
    ).scalar_one_or_none()
    if summary is None:
        summary = MarketSentimentSummary(
            market_id=market.id,
            avg_sentiment=avg_sentiment,
            doc_count=doc_count,
            pos_count=pos_count,
            neg_count=neg_count,
            neutral_count=neutral_count,
            last_computed_at=_utc_now(),
        )
        session.add(summary)
    else:
        summary.avg_sentiment = avg_sentiment
        summary.doc_count = doc_count
        summary.pos_count = pos_count
        summary.neg_count = neg_count
        summary.neutral_count = neutral_count
        summary.last_computed_at = _utc_now()

    session.flush()
    return summary


def get_or_compute_market_sentiment(
    session: Session,
    market_id: str,
) -> SentimentComputationResult | None:
    market = session.execute(
        select(Market)
        .options(joinedload(Market.event))
        .where(Market.market_id == market_id)
    ).unique().scalar_one_or_none()
    if market is None:
        return None

    summary = session.execute(
        select(MarketSentimentSummary).where(MarketSentimentSummary.market_id == market.id)
    ).scalar_one_or_none()
    model_name = settings.sentiment_model_name
    if _is_summary_fresh(summary) and _market_has_current_model_scores(session, market, model_name):
        logger.info("Sentiment cache hit for market %s", market.market_id)
        return SentimentComputationResult(
            market=market,
            summary=summary,
            documents=_get_market_documents(session, market, model_name),
            from_cache=True,
        )

    query = derive_market_query(market)
    cache_state = "stale" if summary is not None else "miss"
    logger.info("Sentiment cache %s for market %s with query '%s'", cache_state, market.market_id, query)

    try:
        candidates = fetch_documents_for_market(query, settings.sentiment_max_docs_per_market)
        logger.info("Fetched %s sentiment candidates for market %s", len(candidates), market.market_id)
        inserted_documents = _upsert_documents(session, market, candidates)
        logger.info("Inserted %s new sentiment documents for market %s", len(inserted_documents), market.market_id)
        market_documents = [
            document
            for document, _score in _get_market_documents(session, market, model_name)
        ]
        scored_count = _score_missing_documents(session, market_documents, model_name)
        logger.info("Scored %s sentiment documents for market %s", scored_count, market.market_id)
        summary = _recompute_summary(session, market, model_name)
        session.commit()
        logger.info(
            "Sentiment summary updated for market %s: docs=%s avg=%s",
            market.market_id,
            summary.doc_count,
            summary.avg_sentiment,
        )
    except IntegrityError as exc:
        session.rollback()
        logger.warning(
            "Sentiment cache race recovered for market %s while writing cache rows: %s",
            market.market_id,
            exc,
        )
        reloaded = _reload_market_sentiment(session, market_id, model_name, from_cache=True)
        if reloaded is not None:
            return reloaded
        raise
    except (SentimentConfigurationError, SentimentUpstreamError, SentimentModelError):
        session.rollback()
        raise
    except Exception:
        session.rollback()
        logger.exception("Unexpected sentiment failure for market %s", market.market_id)
        raise

    refreshed = _reload_market_sentiment(session, market_id, model_name, from_cache=False)
    if refreshed is None:
        logger.error("Sentiment summary missing after refresh for market %s", market.market_id)
        return None
    if refreshed.summary.doc_count == 0:
        logger.warning("No sentiment documents found for market %s", market.market_id)
    return refreshed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sentiment helper commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compute_parser = subparsers.add_parser("compute")
    compute_parser.add_argument("--market-id", required=True)
    return parser


def main(argv: list[str] | None = None, *, session_factory: sessionmaker | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    factory = session_factory or SessionLocal

    with factory() as session:
        if args.command == "compute":
            result = get_or_compute_market_sentiment(session, args.market_id)
            if result is None:
                print("Market not found.")
                return 1
            print(
                f"{result.market.market_id}\tavg={result.summary.avg_sentiment}\t"
                f"docs={result.summary.doc_count}\tcache={result.from_cache}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
