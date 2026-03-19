import type { SignalItem } from "../types";

type SignalListProps = {
  signals: SignalItem[];
  title: string;
  emptyMessage: string;
};

export function SignalList({
  signals,
  title,
  emptyMessage,
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
          {signals.map((signal) => (
            <li key={signal.id} className="signal-card">
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
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
