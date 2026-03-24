export type HealthResponse = {
  status: string;
  timestamp: string;
  version: string;
};

export type MarketSummary = {
  market_id: string;
  event_id: string;
  slug: string | null;
  question: string | null;
  category: string | null;
  has_signals: boolean;
  has_whales: boolean;
  active: boolean | null;
  closed: boolean | null;
  latest_price: number | null;
  latest_volume: number | null;
  latest_snapshot_at: string | null;
};

export type MarketListResponse = {
  items: MarketSummary[];
  limit: number;
  offset: number;
  count: number;
  available_categories: string[];
};

export type MarketOutcome = {
  outcome_index: number;
  outcome_label: string | null;
  current_price: number | null;
  clob_token_id: string | null;
  uma_resolution_status: string | null;
};

export type SnapshotSummary = {
  observed_at: string;
  last_trade_price: number | null;
  volume: number | null;
  liquidity: number | null;
};

export type MarketDetail = {
  market_id: string;
  event_id: string;
  event_api_id: string;
  slug: string | null;
  question: string | null;
  description: string | null;
  resolution_source: string | null;
  market_type: string | null;
  active: boolean | null;
  closed: boolean | null;
  archived: boolean | null;
  restricted: boolean | null;
  latest_snapshot: SnapshotSummary | null;
  outcomes: MarketOutcome[];
};

export type SnapshotHistoryRow = {
  observed_at: string;
  last_trade_price: number | null;
  best_bid: number | null;
  best_ask: number | null;
  volume: number | null;
  liquidity: number | null;
};

export type SnapshotHistoryResponse = {
  market_id: string;
  items: SnapshotHistoryRow[];
  count: number;
};

export type SignalItem = {
  id: number;
  market_id: string;
  event_id: string;
  market_question: string | null;
  market_slug: string | null;
  market_active: boolean | null;
  market_closed: boolean | null;
  signal_type: string;
  signal_strength: number;
  detected_at: string;
  summary: string | null;
  metadata: Record<string, unknown>;
};

export type SignalListResponse = {
  items: SignalItem[];
  limit: number;
  count: number;
};

export type RunItem = {
  id: number;
  status: string;
  trigger_mode: string;
  run_started_at: string;
  run_finished_at: string | null;
  duration_ms: number | null;
  records_fetched: number;
  events_upserted: number;
  markets_upserted: number;
  snapshots_inserted: number;
  records_skipped: number;
  integrity_errors: number;
  error_message: string | null;
};

export type RunListResponse = {
  items: RunItem[];
  limit: number;
  count: number;
};

export type WhaleEvent = {
  id: number;
  market_id: string;
  event_id: string;
  market_question: string | null;
  market_slug: string | null;
  detected_at: string;
  trade_size: number;
  whale_score: number;
  median_multiple: number | null;
  side: string | null;
  outcome_label: string | null;
  proxy_wallet: string | null;
  detection_method: string;
  summary: string | null;
  metadata: Record<string, unknown>;
};

export type WhaleListResponse = {
  items: WhaleEvent[];
  limit: number;
  count: number;
};

export type WhaleSummary = {
  market_id: string;
  total_whale_events: number;
  most_recent_whale_at: string | null;
  largest_whale_trade: number | null;
  average_whale_score: number | null;
  whale_events_24h: number;
  whale_events_7d: number;
  has_recent_whale_activity: boolean;
};

export type WhaleAlertsResponse = {
  status: string;
  message: string;
  alerts: WhaleEvent[];
};

export type MarketSentimentSummary = {
  market_id: string;
  status: "ok" | "empty";
  message: string | null;
  avg_sentiment: number;
  doc_count: number;
  pos_count: number;
  neg_count: number;
  neutral_count: number;
  last_updated: string;
};

export type SentimentDocument = {
  id: number;
  source_name: string | null;
  url: string;
  title: string | null;
  snippet: string | null;
  published_at: string | null;
  sentiment_label: string | null;
  sentiment_confidence: number | null;
  sentiment_value: number | null;
};

export type SentimentDocumentListResponse = {
  market_id: string;
  status: "ok" | "empty";
  message: string | null;
  items: SentimentDocument[];
  count: number;
};

export type ApiErrorDetail = {
  code?: string;
  message?: string;
};
