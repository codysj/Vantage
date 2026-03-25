/*
  Thin typed wrapper over the FastAPI read layer.

  Keeping API access here gives the UI one place to build URLs and one place to
  preserve structured backend errors like sentiment config/unavailable states.
*/

import type {
  ApiErrorDetail,
  HealthResponse,
  MarketDetail,
  MarketListResponse,
  MarketSentimentSummary,
  RunListResponse,
  SentimentDocumentListResponse,
  SignalListResponse,
  SnapshotHistoryResponse,
  WhaleListResponse,
  WhaleAlertsResponse,
  WhaleSummary,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

function buildUrl(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
) {
  const url = new URL(
    path,
    API_BASE_URL.endsWith("/") ? API_BASE_URL : `${API_BASE_URL}/`,
  );
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function fetchJson<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  // preserve API error codes so the sentiment UI can distinguish empty data,
  // configuration issues, and temporary upstream/model failures.
  const response = await fetch(buildUrl(path, params));
  if (!response.ok) {
    let detail: ApiErrorDetail | null = null;
    try {
      detail = (await response.json()).detail as ApiErrorDetail;
    } catch {
      detail = null;
    }
    throw new ApiRequestError(
      detail?.message ?? `Request failed with status ${response.status}`,
      response.status,
      detail?.code,
    );
  }
  return response.json() as Promise<T>;
}

export function getHealth() {
  return fetchJson<HealthResponse>("/health");
}

export function getMarkets(params: {
  limit?: number;
  offset?: number;
  slug?: string;
  active?: boolean;
  closed?: boolean;
  q?: string;
  category?: string;
  has_signals?: boolean;
  signal_type?: string;
}) {
  return fetchJson<MarketListResponse>("/markets", params);
}

export function getMarket(marketId: string) {
  return fetchJson<MarketDetail>(`/markets/${marketId}`);
}

export function getMarketHistory(
  marketId: string,
  params: { limit?: number },
) {
  return fetchJson<SnapshotHistoryResponse>(
    `/markets/${marketId}/history`,
    params,
  );
}

export function getMarketSignals(
  marketId: string,
  params: { limit?: number },
) {
  return fetchJson<SignalListResponse>(
    `/markets/${marketId}/signals`,
    params,
  );
}

export function getSignals(params: {
  limit?: number;
  signal_type?: string;
  market_id?: string;
}) {
  return fetchJson<SignalListResponse>("/signals", params);
}

export function getRecentWhales(params: {
  limit?: number;
  category?: string;
  min_score?: number;
  market_id?: string;
}) {
  return fetchJson<WhaleListResponse>("/whales/recent", params);
}

export function getMarketWhales(
  marketId: string,
  params: { limit?: number },
) {
  return fetchJson<WhaleListResponse>(`/markets/${marketId}/whales`, params);
}

export function getMarketWhaleSummary(marketId: string) {
  return fetchJson<WhaleSummary>(`/markets/${marketId}/whale-summary`);
}

export function getMarketSentiment(marketId: string) {
  return fetchJson<MarketSentimentSummary>(`/markets/${marketId}/sentiment`);
}

export function getMarketSentimentDocuments(marketId: string) {
  return fetchJson<SentimentDocumentListResponse>(
    `/markets/${marketId}/sentiment/documents`,
  );
}

export function getRuns(params: { limit?: number }) {
  return fetchJson<RunListResponse>("/runs", params);
}

export function getWhaleAlerts() {
  return fetchJson<WhaleAlertsResponse>("/whale-alerts");
}
