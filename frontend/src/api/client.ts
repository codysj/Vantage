import type {
  HealthResponse,
  MarketDetail,
  MarketListResponse,
  RunListResponse,
  SignalListResponse,
  SnapshotHistoryResponse,
  WhaleAlertsResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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
  const response = await fetch(buildUrl(path, params));
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
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

export function getRuns(params: { limit?: number }) {
  return fetchJson<RunListResponse>("/runs", params);
}

export function getWhaleAlerts() {
  return fetchJson<WhaleAlertsResponse>("/whale-alerts");
}
