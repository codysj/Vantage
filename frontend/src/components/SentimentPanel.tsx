import { useEffect, useState } from "react";

import {
  ApiRequestError,
  getMarketSentiment,
  getMarketSentimentDocuments,
} from "../api/client";
import type {
  MarketSentimentSummary,
  SentimentDocument,
} from "../types";
import {
  formatDateTime,
  formatRelativeTime,
  formatSignedNumber,
  sentimentToneClass,
} from "../utils/format";

type SentimentPanelProps = {
  marketId: string;
};

export function SentimentPanel({ marketId }: SentimentPanelProps) {
  const [summary, setSummary] = useState<MarketSentimentSummary | null>(null);
  const [documents, setDocuments] = useState<SentimentDocument[]>([]);
  const [status, setStatus] = useState<
    "idle" | "loading" | "loaded" | "empty" | "unavailable" | "error"
  >("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(null);
    setDocuments([]);
    setStatus("idle");
    setError(null);
  }, [marketId]);

  async function handleLoadSentiment() {
    setStatus("loading");
    setError(null);
    setDocuments([]);

    try {
      const summaryResponse = await getMarketSentiment(marketId);
      setSummary(summaryResponse);

      if (summaryResponse.status === "empty" || summaryResponse.doc_count === 0) {
        setStatus("empty");
        return;
      }

      const documentResponse = await getMarketSentimentDocuments(marketId);
      setDocuments(documentResponse.items);
      setStatus(documentResponse.status === "empty" ? "empty" : "loaded");
    } catch (caughtError) {
      if (caughtError instanceof ApiRequestError) {
        if (caughtError.code === "sentiment_config_error") {
          setStatus("unavailable");
          setError("Sentiment is not configured yet.");
          return;
        }
        if (caughtError.code === "sentiment_upstream_unavailable") {
          setStatus("unavailable");
          setError("Headline source is temporarily unavailable.");
          return;
        }
        if (caughtError.code === "sentiment_model_unavailable") {
          setStatus("unavailable");
          setError("Sentiment model is temporarily unavailable.");
          return;
        }
      }
      setStatus("error");
      setError("Unable to load sentiment right now.");
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Market Sentiment</h3>
        <p>On-demand headline sentiment cached per market for fast repeat access.</p>
      </div>

      {status === "idle" ? (
        <div className="sentiment-idle">
          <p>Load recent headlines and cached sentiment for this market when needed.</p>
          <button className="load-more-button" type="button" onClick={handleLoadSentiment}>
            Load sentiment
          </button>
        </div>
      ) : null}

      {status === "loading" ? (
        <div className="list-state">Loading headlines and sentiment...</div>
      ) : null}

      {status === "unavailable" ? <div className="list-state error-state">{error}</div> : null}

      {status === "error" ? <div className="list-state error-state">{error}</div> : null}

      {status === "empty" && summary ? (
        <>
          <div className="whale-summary-grid">
            <div className="status-metric-card">
              <span className="status-metric-label">Average sentiment</span>
              <span className="status-metric-value sentiment-neutral">
                {formatSignedNumber(summary.avg_sentiment)}
              </span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Documents</span>
              <span className="status-metric-value">{summary.doc_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Positive</span>
              <span className="status-metric-value sentiment-positive">{summary.pos_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Negative</span>
              <span className="status-metric-value sentiment-negative">{summary.neg_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Neutral</span>
              <span className="status-metric-value sentiment-neutral">{summary.neutral_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Last updated</span>
              <span className="status-metric-value" title={formatDateTime(summary.last_updated)}>
                {formatRelativeTime(summary.last_updated)}
              </span>
            </div>
          </div>
          <div className="list-state">
            {summary.message ?? "No recent headlines found for this market."}
          </div>
        </>
      ) : null}

      {status === "loaded" && summary ? (
        <>
          <div className="whale-summary-grid">
            <div className="status-metric-card">
              <span className="status-metric-label">Average sentiment</span>
              <span
                className={`status-metric-value ${sentimentToneClass(null, summary.avg_sentiment)}`}
              >
                {formatSignedNumber(summary.avg_sentiment)}
              </span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Documents</span>
              <span className="status-metric-value">{summary.doc_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Positive</span>
              <span className="status-metric-value sentiment-positive">{summary.pos_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Negative</span>
              <span className="status-metric-value sentiment-negative">{summary.neg_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Neutral</span>
              <span className="status-metric-value sentiment-neutral">{summary.neutral_count}</span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Last updated</span>
              <span className="status-metric-value" title={formatDateTime(summary.last_updated)}>
                {formatRelativeTime(summary.last_updated)}
              </span>
            </div>
          </div>

          {documents.length === 0 ? (
            <div className="list-state">No recent headlines found for this market.</div>
          ) : (
            <ul className="signal-list">
              {documents.map((document) => (
                <li key={document.id}>
                  <div className="signal-card sentiment-card">
                    <div className="signal-card-main">
                      <span className="signal-type">{document.source_name ?? "news"}</span>
                      <span
                        className={`signal-strength signal-strength-pill ${sentimentToneClass(
                          document.sentiment_label,
                          document.sentiment_value,
                        )}`}
                      >
                        {document.sentiment_label ?? "unscored"}
                        {document.sentiment_confidence !== null
                          ? ` ${document.sentiment_confidence.toFixed(2)}`
                          : ""}
                      </span>
                    </div>
                    <a
                      className="sentiment-link"
                      href={document.url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {document.title ?? document.url}
                    </a>
                    <p className="signal-context">
                      {document.snippet ?? "No snippet available."}
                    </p>
                    <span className="signal-time" title={formatDateTime(document.published_at)}>
                      {formatRelativeTime(document.published_at)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </div>
  );
}
