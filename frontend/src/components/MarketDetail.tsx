import { useEffect, useState } from "react";

import { getMarket, getMarketHistory, getMarketSignals } from "../api/client";
import type {
  MarketDetail as MarketDetailType,
  SignalItem,
  SnapshotHistoryRow,
} from "../types";
import { PriceChart } from "./PriceChart";
import { SignalList } from "./SignalList";
import { WhaleAlertsPanel } from "./WhaleAlertsPanel";

type MarketDetailProps = {
  marketId: string | null;
};

export function MarketDetail({ marketId }: MarketDetailProps) {
  const [market, setMarket] = useState<MarketDetailType | null>(null);
  const [history, setHistory] = useState<SnapshotHistoryRow[]>([]);
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!marketId) {
      setMarket(null);
      setHistory([]);
      setSignals([]);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getMarket(marketId),
      getMarketHistory(marketId, { limit: 100 }),
      getMarketSignals(marketId, { limit: 10 }),
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

    return () => {
      active = false;
    };
  }, [marketId]);

  if (!marketId) {
    return (
      <div className="panel detail-empty">
        Select a market to inspect its chart and signals.
      </div>
    );
  }

  if (loading) {
    return <div className="panel detail-empty">Loading market detail...</div>;
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
        </div>
        <div className="detail-stats">
          <div className="stat-card">
            <span className="stat-label">Market ID</span>
            <span className="stat-value">{market.market_id}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Latest Price</span>
            <span className="stat-value">
              {market.latest_snapshot?.last_trade_price !== null &&
              market.latest_snapshot
                ? market.latest_snapshot.last_trade_price.toFixed(2)
                : "--"}
            </span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Latest Volume</span>
            <span className="stat-value">
              {market.latest_snapshot?.volume !== null && market.latest_snapshot
                ? market.latest_snapshot.volume.toFixed(2)
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

      <div className="panel">
        <div className="panel-header">
          <h3>Historical Price Chart</h3>
        </div>
        <PriceChart history={history} />
      </div>

      <SignalList
        signals={signals}
        title="Recent Signals"
        emptyMessage="No recent signals for this market."
        showMarketContext={false}
      />

      <WhaleAlertsPanel />
    </div>
  );
}
