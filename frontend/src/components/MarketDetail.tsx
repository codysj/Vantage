/*
  MarketDetail owns the market-level drill-down flow.

  It fetches one market's history, signals, and sentiment resources and then
  passes the combined state into the correlation view and recent-signal list.
*/

import { useEffect, useState } from "react";

import {
  ApiRequestError,
  getMarket,
  getMarketHistory,
  getMarketSentiment,
  getMarketSentimentDocuments,
  getMarketSignals,
} from "../api/client";
import type {
  MarketDetail as MarketDetailType,
  MarketSentimentSummary,
  SentimentDocument,
  SignalItem,
  SnapshotHistoryRow,
} from "../types";
import {
  formatCompactNumber,
  formatDateTime,
  formatProbability,
  formatRelativeTime,
} from "../utils/format";
import { CorrelationPanel } from "./CorrelationPanel";
import { SignalList } from "./SignalList";

type MarketDetailProps = {
  marketId: string | null;
};

export function MarketDetail({ marketId }: MarketDetailProps) {
  const [market, setMarket] = useState<MarketDetailType | null>(null);
  const [history, setHistory] = useState<SnapshotHistoryRow[]>([]);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [sentimentSummary, setSentimentSummary] = useState<MarketSentimentSummary | null>(null);
  const [sentimentDocuments, setSentimentDocuments] = useState<SentimentDocument[]>([]);
  const [sentimentStatus, setSentimentStatus] = useState<
    | "readLoading"
    | "hasCachedData"
    | "noDataYet"
    | "generationInProgress"
    | "configError"
    | "unavailable"
    | "error"
  >("readLoading");
  const [sentimentMessage, setSentimentMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!marketId) {
      setMarket(null);
      setHistory([]);
      setSignals([]);
      setSentimentSummary(null);
      setSentimentDocuments([]);
      setSentimentStatus("readLoading");
      setSentimentMessage(null);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);
    setSentimentSummary(null);
    setSentimentDocuments([]);
    setSentimentStatus("readLoading");
    setSentimentMessage(null);

    // price history and market-specific signals are core detail data, so they
    // load together and block the detail shell.
    Promise.all([
      getMarket(marketId),
      getMarketHistory(marketId, { limit: 100 }),
      getMarketSignals(marketId, { limit: 50 }),
    ])
      .then(([marketResponse, historyResponse, signalsResponse]) => {
        if (!active) {
          return;
        }

        setMarket(marketResponse);
        setHistory(historyResponse.items);
        setSignals(signalsResponse.items);
      })
      .catch(() => {
        if (active) {
          setError("Unable to load market detail right now.");
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    // sentiment is enrichment, not a hard dependency. We load it separately so
    // the detail panel can still render price history and signals without it.
    getMarketSentiment(marketId)
      .then((summaryResponse) => {
        if (!active) {
          return;
        }

        setSentimentSummary(summaryResponse);
        if (summaryResponse.status === "empty" || summaryResponse.doc_count === 0) {
          setSentimentStatus("noDataYet");
          setSentimentMessage(summaryResponse.message ?? "No sentiment data available yet for this market.");
          return;
        }

        // only fetch per-headline documents when cached sentiment actually
        // exists for this market.
        getMarketSentimentDocuments(marketId)
          .then((documentsResponse) => {
            if (!active) {
              return;
            }

            setSentimentDocuments(documentsResponse.items);
            setSentimentStatus("hasCachedData");
          })
          .catch((caughtError) => {
            if (!active) {
              return;
            }
            if (caughtError instanceof ApiRequestError) {
              setSentimentStatus(
                caughtError.code === "sentiment_config_error"
                  ? "configError"
                  : caughtError.code === "sentiment_upstream_unavailable" ||
                      caughtError.code === "sentiment_model_unavailable"
                    ? "unavailable"
                    : "error",
              );
              setSentimentMessage(caughtError.message);
              return;
            }
            setSentimentStatus("error");
            setSentimentMessage("Unable to load sentiment details right now.");
          });
      })
      .catch((caughtError) => {
        if (!active) {
          return;
        }
        if (caughtError instanceof ApiRequestError) {
          setSentimentStatus(
            caughtError.code === "sentiment_config_error"
              ? "configError"
              : caughtError.code === "sentiment_upstream_unavailable" ||
                  caughtError.code === "sentiment_model_unavailable"
                ? "unavailable"
                : "error",
          );
          setSentimentMessage(caughtError.message);
          return;
        }
        setSentimentStatus("error");
        setSentimentMessage("Unable to load sentiment right now.");
      });

    return () => {
      active = false;
    };
  }, [marketId]);

  async function handleGenerateSentiment() {
    if (!marketId) {
      return;
    }

    setSentimentStatus("generationInProgress");
    setSentimentMessage(null);

    try {
      // this reuses the Phase 6 lazy endpoint: a cache miss can trigger fetch,
      // inference, and storage, then the detail view refreshes from that cache.
      const summaryResponse = await getMarketSentiment(marketId);
      setSentimentSummary(summaryResponse);

      if (summaryResponse.status === "empty" || summaryResponse.doc_count === 0) {
        setSentimentDocuments([]);
        setSentimentStatus("noDataYet");
        setSentimentMessage(summaryResponse.message ?? "No sentiment data available yet for this market.");
        return;
      }

      const documentsResponse = await getMarketSentimentDocuments(marketId);
      setSentimentDocuments(documentsResponse.items);
      setSentimentStatus("hasCachedData");
    } catch (caughtError) {
      if (caughtError instanceof ApiRequestError) {
        setSentimentStatus(
          caughtError.code === "sentiment_config_error"
            ? "configError"
            : caughtError.code === "sentiment_upstream_unavailable" ||
                caughtError.code === "sentiment_model_unavailable"
              ? "unavailable"
              : "error",
        );
        setSentimentMessage(caughtError.message);
        return;
      }

      setSentimentStatus("error");
      setSentimentMessage("Unable to generate sentiment context right now.");
    }
  }

  if (!marketId) {
    return (
      <div className="panel detail-empty">
        Select a market from the browser or signal feed to inspect its chart,
        metadata, and recent alerts.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="panel detail-empty">
        Loading market detail, chart history, and recent signals...
      </div>
    );
  }

  if (error) {
    return <div className="panel detail-empty error-state">{error}</div>;
  }

  if (!market) {
    return <div className="panel detail-empty">Market detail is unavailable.</div>;
  }

  return (
    <div className="detail-stack">
      <div className="panel detail-header-panel">
        <div className="panel-header">
          <h2>{market.question ?? market.slug ?? market.market_id}</h2>
          <p>{market.description ?? "No description available."}</p>
          <p className="detail-freshness">
            Latest snapshot{" "}
            <span title={formatDateTime(market.latest_snapshot?.observed_at ?? null)}>
              {formatRelativeTime(market.latest_snapshot?.observed_at ?? null)}
            </span>
          </p>
        </div>
        <div className="detail-stats">
          <div className="stat-card stat-card-emphasis">
            <span className="stat-label">Latest Price</span>
            <span className="stat-value stat-value-emphasis">
              {market.latest_snapshot?.last_trade_price !== null &&
              market.latest_snapshot
                ? formatProbability(market.latest_snapshot.last_trade_price)
                : "--"}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Market ID</span>
            <span className="stat-value">{market.market_id}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Latest Volume</span>
            <span className="stat-value">
              {market.latest_snapshot?.volume !== null && market.latest_snapshot
                ? formatCompactNumber(market.latest_snapshot.volume)
                : "--"}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Latest Liquidity</span>
            <span className="stat-value">
              {market.latest_snapshot?.liquidity !== null &&
              market.latest_snapshot
                ? formatCompactNumber(market.latest_snapshot.liquidity)
                : "--"}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Status</span>
            <span className="stat-value">
              {market.closed ? "Closed" : market.active ? "Active" : "Unknown"}
            </span>
          </div>
        </div>
      </div>

      <CorrelationPanel
        history={history}
        signals={signals}
        sentimentSummary={sentimentSummary}
        sentimentDocuments={sentimentDocuments}
        sentimentStatus={sentimentStatus}
        sentimentMessage={sentimentMessage}
        onGenerateSentiment={handleGenerateSentiment}
      />

      <SignalList
        signals={signals}
        title="Recent Signals"
        emptyMessage="No recent signals for this market."
        showMarketContext={false}
      />
    </div>
  );
}
