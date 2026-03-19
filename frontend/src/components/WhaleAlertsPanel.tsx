import { useEffect, useState } from "react";

import { getMarketWhaleSummary, getMarketWhales } from "../api/client";
import type { WhaleEvent, WhaleSummary } from "../types";
import {
  formatCompactNumber,
  formatDateTime,
  formatRelativeTime,
} from "../utils/format";

type WhaleAlertsPanelProps = {
  marketId: string;
};

export function WhaleAlertsPanel({ marketId }: WhaleAlertsPanelProps) {
  const [summary, setSummary] = useState<WhaleSummary | null>(null);
  const [whales, setWhales] = useState<WhaleEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([
      getMarketWhales(marketId, { limit: 8 }),
      getMarketWhaleSummary(marketId),
    ])
      .then(([whalesResponse, summaryResponse]) => {
        if (!active) {
          return;
        }
        setWhales(whalesResponse.items);
        setSummary(summaryResponse);
      })
      .catch(() => {
        if (active) {
          setError("Unable to load whale activity right now.");
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

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Whale Activity</h3>
        <p>Unusually large trades versus this market's recent trade-size baseline.</p>
      </div>
      {loading ? <div className="list-state">Loading whale activity...</div> : null}
      {error ? <div className="list-state error-state">{error}</div> : null}
      {!loading && !error && summary ? (
        <>
          <div className="whale-summary-grid">
            <div className="status-metric-card">
              <span className="status-metric-label">Total whale events</span>
              <span className="status-metric-value">
                {summary.total_whale_events}
              </span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Recent whale activity</span>
              <span
                className="status-metric-value"
                title={formatDateTime(summary.most_recent_whale_at)}
              >
                {formatRelativeTime(summary.most_recent_whale_at)}
              </span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Largest whale trade</span>
              <span className="status-metric-value">
                {summary.largest_whale_trade !== null
                  ? formatCompactNumber(summary.largest_whale_trade)
                  : "--"}
              </span>
            </div>
            <div className="status-metric-card">
              <span className="status-metric-label">Avg. whale score</span>
              <span className="status-metric-value">
                {summary.average_whale_score !== null
                  ? summary.average_whale_score.toFixed(2)
                  : "--"}
              </span>
            </div>
          </div>

          {whales.length === 0 ? (
            <div className="list-state">No whale events detected for this market yet.</div>
          ) : (
            <ul className="signal-list">
              {whales.map((whale) => (
                <li key={whale.id}>
                  <div className="signal-card whale-card">
                    <div className="signal-card-main">
                      <span className="signal-type">whale</span>
                      <span className="signal-strength signal-strength-pill signal-strength-high">
                        {whale.whale_score.toFixed(2)}
                      </span>
                    </div>
                    <p className="signal-summary">
                      {whale.summary ?? "Large trade detected versus market baseline."}
                    </p>
                    <p className="signal-context">
                      Size {formatCompactNumber(whale.trade_size)}
                      {whale.median_multiple !== null
                        ? ` | ${whale.median_multiple.toFixed(2)}x median`
                        : ""}
                      {whale.outcome_label ? ` | ${whale.outcome_label}` : ""}
                    </p>
                    <span className="signal-time" title={formatDateTime(whale.detected_at)}>
                      {formatRelativeTime(whale.detected_at)}
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
