import type { SignalItem } from "../types";

type SignalListProps = {
  signals: SignalItem[];
  title: string;
  emptyMessage: string;
  onSelectMarket?: (marketId: string) => void;
  selectedMarketId?: string | null;
  showMarketContext?: boolean;
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
}: SignalListProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h3>{title}</h3>
      </div>
      {signals.length === 0 ? (
        <div className="list-state">{emptyMessage}</div>
      ) : (
        <ul className="signal-list">
          {signals.map((signal) => {
            const clickable = Boolean(onSelectMarket);
            const selected = selectedMarketId === signal.market_id;
            const marketStatus = statusLabel(signal);
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
                  <span className="signal-strength">
                    {signal.signal_strength.toFixed(2)}
                  </span>
                </div>
                <p>{signal.summary ?? "No summary available."}</p>
                <span className="signal-time">
                  {new Date(signal.detected_at).toLocaleString()}
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
