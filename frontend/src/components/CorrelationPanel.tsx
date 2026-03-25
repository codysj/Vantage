import { useMemo, useState } from "react";
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  MarketSentimentSummary,
  SentimentDocument,
  SignalItem,
  SnapshotHistoryRow,
} from "../types";
import {
  formatDateTime,
  formatProbability,
  formatRelativeTime,
  formatSignedNumber,
  sentimentToneClass,
  signalStrengthTier,
} from "../utils/format";
import { buildCorrelationView } from "../utils/correlation";

type CorrelationPanelProps = {
  history: SnapshotHistoryRow[];
  signals: SignalItem[];
  sentimentSummary: MarketSentimentSummary | null;
  sentimentDocuments: SentimentDocument[];
  sentimentStatus:
    | "readLoading"
    | "hasCachedData"
    | "noDataYet"
    | "generationInProgress"
    | "configError"
    | "unavailable"
    | "error";
  sentimentMessage: string | null;
  onGenerateSentiment: () => void;
};

function formatTick(timestamp: number) {
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
  });
}

function renderDiamond(props: { cx?: number; cy?: number; fill?: string }) {
  const { cx = 0, cy = 0, fill = "#b66a17" } = props;
  return (
    <path
      d={`M ${cx} ${cy - 7} L ${cx + 7} ${cy} L ${cx} ${cy + 7} L ${cx - 7} ${cy} Z`}
      fill={fill}
      stroke="#ffffff"
      strokeWidth={1.5}
    />
  );
}

function CorrelationTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload: any }>; label?: number }) {
  if (!active || !payload || payload.length === 0 || label === undefined) {
    return null;
  }

  const row = payload[0]?.payload;
  if (!row) {
    return null;
  }

  if ("signal_type" in row) {
    return (
      <div className="correlation-tooltip">
        <strong>{formatDateTime(new Date(row.timestamp).toISOString())}</strong>
        <div>Event: {row.signal_type}</div>
        <div>Severity: {row.signal_strength.toFixed(2)}</div>
        <div>{row.summary ?? "Event marker"}</div>
      </div>
    );
  }

  return (
    <div className="correlation-tooltip">
      <strong>{formatDateTime(new Date(label).toISOString())}</strong>
      <div>Price: {row.price !== null ? row.price.toFixed(2) : "--"}</div>
      <div>Sentiment: {row.sentiment !== null ? formatSignedNumber(row.sentiment) : "--"}</div>
      <div>Sentiment docs: {row.docCount}</div>
      {row.anomalies.length > 0 ? (
        <div>Signals: {row.anomalies.map((signal: SignalItem) => signal.signal_type).join(", ")}</div>
      ) : null}
      {row.whales.length > 0 ? <div>Whales: {row.whales.length}</div> : null}
    </div>
  );
}

function correlationTone(sentimentStatus: CorrelationPanelProps["sentimentStatus"]) {
  if (
    sentimentStatus === "configError" ||
    sentimentStatus === "unavailable" ||
    sentimentStatus === "error"
  ) {
    return "error-state";
  }
  return "";
}

export function CorrelationPanel({
  history,
  signals,
  sentimentSummary,
  sentimentDocuments,
  sentimentStatus,
  sentimentMessage,
  onGenerateSentiment,
}: CorrelationPanelProps) {
  const [showSentiment, setShowSentiment] = useState(true);
  const [showAnomalies, setShowAnomalies] = useState(true);
  const [showWhales, setShowWhales] = useState(true);

  const correlation = useMemo(
    () =>
      buildCorrelationView({
        history,
        signals,
        sentimentSummary,
        sentimentDocuments,
      }),
    [history, signals, sentimentDocuments, sentimentSummary],
  );

  const anomalyMarkers = correlation.rows
    .filter((row) => row.markerPrice !== null && row.anomalies.length > 0)
    .flatMap((row) =>
      row.anomalies.map((signal) => ({
        timestamp: row.timestamp,
        markerPrice: row.markerPrice as number,
        signal_type: signal.signal_type,
        signal_strength: signal.signal_strength,
        summary: signal.summary,
        metadata: signal.metadata,
      })),
    );

  const whaleMarkers = correlation.rows
    .filter((row) => row.markerPrice !== null && row.whales.length > 0)
    .flatMap((row) =>
      row.whales.map((signal) => ({
        timestamp: row.timestamp,
        markerPrice: row.markerPrice as number,
        signal_type: signal.signal_type,
        signal_strength: signal.signal_strength,
        summary: signal.summary,
        metadata: signal.metadata,
      })),
    );

  const hasPriceHistory = correlation.rows.some((row) => row.price !== null);

  return (
    <div className="panel">
      <div className="panel-header correlation-panel-header">
        <div>
          <h3>Correlation View</h3>
          <p>Compare price movement, sentiment trend, and event markers on one timeline.</p>
        </div>
        <div className="correlation-toggle-row">
          <button
            type="button"
            className={`chip ${showSentiment ? "chip-active" : ""}`}
            onClick={() => setShowSentiment((current) => !current)}
          >
            Sentiment
          </button>
          <button
            type="button"
            className={`chip ${showAnomalies ? "chip-active" : ""}`}
            onClick={() => setShowAnomalies((current) => !current)}
          >
            Anomalies
          </button>
          <button
            type="button"
            className={`chip ${showWhales ? "chip-active" : ""}`}
            onClick={() => setShowWhales((current) => !current)}
          >
            Whales
          </button>
        </div>
      </div>

      <div className="correlation-summary-grid">
        <div className="status-metric-card">
          <span className="status-metric-label">Latest price</span>
          <span className="status-metric-value">
            {formatProbability(history[history.length - 1]?.last_trade_price ?? null)}
          </span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Latest sentiment</span>
          <span
            className={`status-metric-value ${sentimentToneClass(
              null,
              correlation.latestSentiment,
            )}`}
          >
            {formatSignedNumber(correlation.latestSentiment)}
          </span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Sentiment docs</span>
          <span className="status-metric-value">{correlation.sentimentDocCount}</span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Recent anomalies</span>
          <span className="status-metric-value">{correlation.anomalyCount}</span>
        </div>
        <div className="status-metric-card">
          <span className="status-metric-label">Recent whales</span>
          <span className="status-metric-value">{correlation.whaleCount}</span>
        </div>
      </div>

      {!hasPriceHistory ? (
        <div className="chart-empty">No history yet for this market.</div>
      ) : (
        <div className="correlation-chart-shell" data-testid="correlation-panel">
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={correlation.rows} syncId="market-correlation">
              <XAxis
                dataKey="timestamp"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={formatTick}
                hide
              />
              <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} />
              <Tooltip content={<CorrelationTooltip />} />
              <ReferenceLine y={0.5} stroke="#d8dde8" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="price"
                stroke="#1565c0"
                strokeWidth={2.5}
                dot={false}
                connectNulls
                name="Price"
              />
              {showAnomalies ? (
                <Scatter
                  name="Anomalies"
                  data={anomalyMarkers}
                  dataKey="markerPrice"
                  fill="#0f5cc0"
                  shape="circle"
                />
              ) : null}
              {showWhales ? (
                <Scatter
                  name="Whales"
                  data={whaleMarkers}
                  dataKey="markerPrice"
                  fill="#b66a17"
                  shape={renderDiamond}
                />
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>

          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={correlation.rows} syncId="market-correlation">
              <XAxis
                dataKey="timestamp"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={formatTick}
                tick={{ fontSize: 12 }}
              />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 12 }} />
              <Tooltip content={<CorrelationTooltip />} />
              <ReferenceLine y={0} stroke="#94a6ba" strokeDasharray="4 4" />
              {showSentiment ? (
                <>
                  <Area
                    type="monotone"
                    dataKey="sentiment"
                    stroke="#4c6988"
                    fill="#d6e6f6"
                    fillOpacity={0.75}
                    connectNulls
                  />
                  <Line
                    type="monotone"
                    dataKey="sentiment"
                    stroke="#173b66"
                    strokeWidth={2}
                    dot={(props) =>
                      props.payload?.docCount ? (
                        <circle
                          cx={props.cx}
                          cy={props.cy}
                          r={Math.min(7, 3 + props.payload.docCount)}
                          fill="#173b66"
                          stroke="#ffffff"
                          strokeWidth={1.5}
                        />
                      ) : (
                        <></>
                      )
                    }
                    connectNulls
                  />
                </>
              ) : null}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="correlation-legend">
        <span><i className="legend-swatch legend-price" /> Price</span>
        <span><i className="legend-swatch legend-sentiment" /> Sentiment</span>
        <span><i className="legend-swatch legend-anomaly" /> Anomaly signal</span>
        <span><i className="legend-swatch legend-whale" /> Whale event</span>
      </div>

      {sentimentStatus === "readLoading" ? (
        <div className="list-state">Loading cached sentiment and headlines...</div>
      ) : null}

      {sentimentStatus === "noDataYet" ? (
        <div className="sentiment-empty-cta">
          <p>No sentiment data available yet for this market.</p>
          <button className="load-more-button" type="button" onClick={onGenerateSentiment}>
            Load sentiment drivers
          </button>
        </div>
      ) : null}

      {sentimentStatus === "generationInProgress" ? (
        <div className="sentiment-empty-cta">
          <p>Generating sentiment context...</p>
          <button className="load-more-button" type="button" disabled>
            Generating sentiment context...
          </button>
        </div>
      ) : null}

      {sentimentStatus === "configError" ||
      sentimentStatus === "unavailable" ||
      sentimentStatus === "error" ? (
        <div className={`list-state ${correlationTone(sentimentStatus)}`}>
          {sentimentMessage ?? "Sentiment is temporarily unavailable for this market."}
        </div>
      ) : null}

      {showSentiment &&
      sentimentStatus === "hasCachedData" &&
      correlation.recentHeadlines.length > 0 ? (
        <div className="correlation-headlines">
          <div className="panel-header">
            <h3>Recent Sentiment Headlines</h3>
            <p>Recent scored headlines used for this market&apos;s cached sentiment view.</p>
          </div>
          <ul className="signal-list">
            {correlation.recentHeadlines.map((document) => (
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
                  <p className="signal-context">{document.snippet ?? "No snippet available."}</p>
                  <span className="signal-time" title={formatDateTime(document.published_at)}>
                    {formatRelativeTime(document.published_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="correlation-marker-summary">
        {showAnomalies && anomalyMarkers.length > 0 ? (
          <span>
            Latest anomaly: {anomalyMarkers[anomalyMarkers.length - 1].signal_type} (
            {signalStrengthTier(
              anomalyMarkers[anomalyMarkers.length - 1].signal_type,
              anomalyMarkers[anomalyMarkers.length - 1].signal_strength,
            )}
            )
          </span>
        ) : null}
        {showWhales && whaleMarkers.length > 0 ? (
          <span>
            Largest whale marker score:{" "}
            {Math.max(...whaleMarkers.map((marker) => marker.signal_strength)).toFixed(2)}
          </span>
        ) : null}
      </div>
    </div>
  );
}
