import type { HealthResponse, RunItem } from "../types";

type SystemStatusPanelProps = {
  runs: RunItem[];
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
  healthError: string | null;
};

function formatDuration(durationMs: number | null) {
  if (!durationMs || durationMs <= 0) {
    return "--";
  }

  if (durationMs >= 1000) {
    return `${(durationMs / 1000).toFixed(1)}s`;
  }

  return `${durationMs}ms`;
}

function formatDate(value: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString();
}

function relativeTime(value: string | null) {
  if (!value) {
    return "No successful sweep recorded yet.";
  }

  const diffMs = Date.now() - new Date(value).getTime();
  if (Number.isNaN(diffMs) || diffMs < 0) {
    return `Updated at ${formatDate(value)}`;
  }

  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 1) {
    return "Updated less than a minute ago.";
  }
  if (diffMinutes < 60) {
    return `Updated ${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago.`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `Updated ${diffHours} hour${diffHours === 1 ? "" : "s"} ago.`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `Updated ${diffDays} day${diffDays === 1 ? "" : "s"} ago.`;
}

function deriveStatus(
  latestRun: RunItem | null,
  healthError: string | null,
): { label: string; className: string } {
  if (healthError) {
    return { label: "Error", className: "status-badge closed" };
  }

  if (!latestRun) {
    return { label: "Waiting", className: "status-badge neutral" };
  }

  if (latestRun.status === "success") {
    return { label: "Healthy", className: "status-badge active" };
  }

  if (latestRun.status === "failed") {
    return { label: "Error", className: "status-badge closed" };
  }

  return { label: "Warning", className: "status-badge warning" };
}

export function SystemStatusPanel({
  runs,
  health,
  loading,
  error,
  healthError,
}: SystemStatusPanelProps) {
  const latestRun = runs[0] ?? null;
  const latestSuccessfulRun = runs.find((run) => run.status === "success") ?? null;
  const status = deriveStatus(latestRun, healthError);

  if (loading) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h3>System Status</h3>
          <p>Checking pipeline freshness and backend health.</p>
        </div>
        <div className="list-state">Loading pipeline status...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h3>System Status</h3>
          <p>Checking pipeline freshness and backend health.</p>
        </div>
        <div className="list-state error-state">{error}</div>
      </div>
    );
  }

  if (!latestRun) {
    return (
      <div className="panel">
        <div className="panel-header">
          <h3>System Status</h3>
          <p>Checking pipeline freshness and backend health.</p>
        </div>
        <div className="system-status-header">
          <span className={status.className}>{status.label}</span>
        </div>
        <div className="list-state">
          No ingestion runs recorded yet. Start the pipeline to populate status
          metrics and freshness data.
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>System Status</h3>
        <p>Current pipeline health, freshness, and latest sweep summary.</p>
      </div>

      <div className="system-status-header">
        <span className={status.className}>{status.label}</span>
        <div className="system-status-copy">
          <strong>{relativeTime(latestSuccessfulRun?.run_finished_at ?? latestSuccessfulRun?.run_started_at ?? null)}</strong>
          <span>
            API {healthError ? "unavailable" : health?.status ?? "unknown"}
          </span>
        </div>
      </div>

      <div className="status-metric-grid">
        <div className="status-metric-card">
          <span className="status-metric-label">Last successful sweep</span>
          <span className="status-metric-value">
            {formatDate(
              latestSuccessfulRun?.run_finished_at ??
                latestSuccessfulRun?.run_started_at ??
                null,
            )}
          </span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Latest run duration</span>
          <span className="status-metric-value">
            {formatDuration(latestRun.duration_ms)}
          </span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Markets processed</span>
          <span className="status-metric-value">
            {latestRun.markets_upserted || latestRun.records_fetched}
          </span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Snapshots written</span>
          <span className="status-metric-value">{latestRun.snapshots_inserted}</span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Records skipped</span>
          <span className="status-metric-value">{latestRun.records_skipped}</span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Integrity issues</span>
          <span className="status-metric-value">{latestRun.integrity_errors}</span>
        </div>
      </div>

      <div className="system-status-footer">
        <span>Latest trigger: {latestRun.trigger_mode}</span>
        <span>
          Latest sweep started {formatDate(latestRun.run_started_at)}
        </span>
      </div>
    </div>
  );
}
