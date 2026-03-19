import type { RunItem } from "../types";

type RunsPanelProps = {
  runs: RunItem[];
  loading: boolean;
  error: string | null;
};

export function RunsPanel({ runs, loading, error }: RunsPanelProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Pipeline Runs</h3>
      </div>
      {loading ? <div className="list-state">Loading recent runs...</div> : null}
      {error ? <div className="list-state error-state">{error}</div> : null}
      {!loading && !error && runs.length === 0 ? (
        <div className="list-state">No ingestion runs recorded yet.</div>
      ) : null}
      {!loading && !error && runs.length > 0 ? (
        <ul className="run-list">
          {runs.map((run) => (
            <li key={run.id} className="run-card">
              <div className="run-card-main">
                <span
                  className={
                    run.status === "success"
                      ? "status-badge active"
                      : "status-badge closed"
                  }
                >
                  {run.status}
                </span>
                <span>{new Date(run.run_started_at).toLocaleString()}</span>
              </div>
              <div className="run-card-meta">
                <span>Fetched {run.records_fetched}</span>
                <span>Snapshots {run.snapshots_inserted}</span>
                <span>Duration {run.duration_ms ?? 0} ms</span>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
