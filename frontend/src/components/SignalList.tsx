import type { SignalItem } from "../types";
import {
  formatDateTime,
  formatRelativeTime,
  signalContext,
  signalStrengthTier,
} from "../utils/format";

type SignalListProps = {
  signals: SignalItem[];
  title: string;
  emptyMessage: string;
  onSelectMarket?: (marketId: string) => void;
  selectedMarketId?: string | null;
  showMarketContext?: boolean;
  sortByStrength?: boolean;
};

function marketLabel(signal: SignalItem) {
  return signal.market_question ?? signal.market_slug ?? signal.market_id;
}

function secondaryMarketLabel(signal: SignalItem) {
  if (signal.market_question && signal.market_slug) {
    return signal.market_slug;
  }

  if (signal.market_question && !signal.market_slug) {
    return signal.market_id;
  }

  return null;
}

function statusLabel(signal: SignalItem) {
  if (signal.market_closed) {
    return "Closed";
  }
  if (signal.market_active) {
    return "Active";
  }
  return null;
}

export function SignalList({
  signals,
  title,
  emptyMessage,
  onSelectMarket,
  selectedMarketId = null,
  showMarketContext = false,
  sortByStrength = false,
}: SignalListProps) {
  const visibleSignals = sortByStrength
    ? [...signals].sort((left, right) => {
        if (right.signal_strength !== left.signal_strength) {
          return right.signal_strength - left.signal_strength;
        }
        return (
          new Date(right.detected_at).getTime() - new Date(left.detected_at).getTime()
        );
      })
    : signals;

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>{title}</h3>
      </div>
      {visibleSignals.length === 0 ? (
        <div className="list-state">{emptyMessage}</div>
      ) : (
        <ul className="signal-list">
          {visibleSignals.map((signal) => {
            const clickable = Boolean(onSelectMarket);
            const selected = selectedMarketId === signal.market_id;
            const marketStatus = statusLabel(signal);
            const strengthTier = signalStrengthTier(
              signal.signal_type,
              signal.signal_strength,
            );
            const cardClassName = [
              "signal-card",
              clickable ? "signal-card-clickable" : "",
              selected ? "signal-card-selected" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const content = (
              <>
                {showMarketContext ? (
                  <div className="signal-market-row">
                    <div className="signal-market-copy">
                      <span className="signal-market-title">{marketLabel(signal)}</span>
                      {secondaryMarketLabel(signal) ? (
                        <span className="signal-market-subtitle">
                          {secondaryMarketLabel(signal)}
                        </span>
                      ) : null}
                    </div>
                    {marketStatus ? (
                      <span
                        className={
                          signal.market_closed
                            ? "status-badge closed"
                            : "status-badge active"
                        }
                      >
                        {marketStatus}
                      </span>
                    ) : null}
                  </div>
                ) : null}
                <div className="signal-card-main">
                  <span className="signal-type">{signal.signal_type}</span>
                  <span
                    className={`signal-strength signal-strength-pill signal-strength-${strengthTier}`}
                  >
                    {strengthTier} · {signal.signal_strength.toFixed(2)}
                  </span>
                </div>
                <p className="signal-summary">{signal.summary ?? "No summary available."}</p>
                <p className="signal-context">{signalContext(signal.signal_type)}</p>
                <span className="signal-time" title={formatDateTime(signal.detected_at)}>
                  {formatRelativeTime(signal.detected_at)}
                </span>
              </>
            );

            return (
              <li key={signal.id}>
                {clickable ? (
                  <button
                    type="button"
                    className={cardClassName}
                    onClick={() => onSelectMarket?.(signal.market_id)}
                  >
                    {content}
                  </button>
                ) : (
                  <div className={cardClassName}>{content}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
