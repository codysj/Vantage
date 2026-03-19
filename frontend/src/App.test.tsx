import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const healthResponse = {
  status: "ok",
  timestamp: "2026-03-18T12:00:00Z",
  version: "0.4.0",
};

const marketsResponse = {
  items: [
    {
      market_id: "market-1",
      event_id: "event-1",
      slug: "will-fed-cut-rates-june",
      question: "Will the Fed cut rates in June?",
      active: true,
      closed: false,
      latest_price: 0.43,
      latest_volume: 150,
      latest_snapshot_at: "2026-03-18T12:00:00Z",
    },
    {
      market_id: "market-2",
      event_id: "event-2",
      slug: "will-cpi-rise-april",
      question: "Will CPI rise in April?",
      active: true,
      closed: false,
      latest_price: 0.61,
      latest_volume: 210,
      latest_snapshot_at: "2026-03-18T12:05:00Z",
    },
  ],
  limit: 20,
  offset: 0,
  count: 2,
};

const marketDetailResponse = {
  market_id: "market-1",
  event_id: "1",
  event_api_id: "event-1",
  slug: "will-fed-cut-rates-june",
  question: "Will the Fed cut rates in June?",
  description: "Rates market",
  resolution_source: null,
  market_type: null,
  active: true,
  closed: false,
  archived: false,
  restricted: false,
  latest_snapshot: {
    observed_at: "2026-03-18T12:00:00Z",
    last_trade_price: 0.43,
    volume: 150,
    liquidity: 200,
  },
  outcomes: [],
};

const secondMarketDetailResponse = {
  market_id: "market-2",
  event_id: "2",
  event_api_id: "event-2",
  slug: "will-cpi-rise-april",
  question: "Will CPI rise in April?",
  description: "Inflation market",
  resolution_source: null,
  market_type: null,
  active: true,
  closed: false,
  archived: false,
  restricted: false,
  latest_snapshot: {
    observed_at: "2026-03-18T12:05:00Z",
    last_trade_price: 0.61,
    volume: 210,
    liquidity: 140,
  },
  outcomes: [],
};

const historyResponse = {
  market_id: "market-1",
  items: [
    {
      observed_at: "2026-03-18T11:55:00Z",
      last_trade_price: 0.33,
      best_bid: 0.32,
      best_ask: 0.34,
      volume: 100,
      liquidity: 180,
    },
  ],
  count: 1,
};

const signalsResponse = {
  items: [
    {
      id: 1,
      market_id: "market-1",
      event_id: "event-1",
      market_question: "Will the Fed cut rates in June?",
      market_slug: "will-fed-cut-rates-june",
      market_active: true,
      market_closed: false,
      signal_type: "price_movement",
      signal_strength: 0.2,
      detected_at: "2026-03-18T12:00:00Z",
      summary: "Price moved 20%",
      metadata: { summary: "Price moved 20%" },
    },
    {
      id: 2,
      market_id: "market-2",
      event_id: "event-2",
      market_question: "Will CPI rise in April?",
      market_slug: "will-cpi-rise-april",
      market_active: true,
      market_closed: false,
      signal_type: "volume_spike",
      signal_strength: 3.4,
      detected_at: "2026-03-18T12:05:00Z",
      summary: "Volume jumped versus baseline",
      metadata: { summary: "Volume jumped versus baseline" },
    },
  ],
  limit: 10,
  count: 2,
};

const runsResponse = {
  items: [
    {
      id: 1,
      status: "success",
      trigger_mode: "manual",
      run_started_at: "2026-03-18T12:00:00Z",
      run_finished_at: "2026-03-18T12:00:10Z",
      duration_ms: 10000,
      records_fetched: 20,
      events_upserted: 5,
      markets_upserted: 5,
      snapshots_inserted: 10,
      records_skipped: 0,
      integrity_errors: 0,
      error_message: null,
    },
  ],
  limit: 6,
  count: 1,
};

const whaleResponse = {
  status: "unavailable",
  message: "Trade ingestion is not active yet; whale alerts are deferred.",
  alerts: [],
};

function installFetchMock(overrides?: {
  history?: typeof historyResponse;
  signals?: typeof signalsResponse;
  marketsStatus?: number;
}) {
  const mockFetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes("/health")) {
      return Promise.resolve(new Response(JSON.stringify(healthResponse), { status: 200 }));
    }
    if (url.includes("/markets?")) {
      const status = overrides?.marketsStatus ?? 200;
      return Promise.resolve(
        new Response(
          status === 200 ? JSON.stringify(marketsResponse) : "error",
          { status },
        ),
      );
    }
    if (url.endsWith("/markets/market-1")) {
      return Promise.resolve(
        new Response(JSON.stringify(marketDetailResponse), { status: 200 }),
      );
    }
    if (url.endsWith("/markets/market-2")) {
      return Promise.resolve(
        new Response(JSON.stringify(secondMarketDetailResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-1/history")) {
      return Promise.resolve(
        new Response(
          JSON.stringify(overrides?.history ?? historyResponse),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/markets/market-2/history")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            market_id: "market-2",
            items: [
              {
                observed_at: "2026-03-18T12:00:00Z",
                last_trade_price: 0.55,
                best_bid: 0.54,
                best_ask: 0.56,
                volume: 130,
                liquidity: 130,
              },
            ],
            count: 1,
          }),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/markets/market-1/signals")) {
      return Promise.resolve(
        new Response(JSON.stringify(overrides?.signals ?? signalsResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-2/signals")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              {
                id: 22,
                market_id: "market-2",
                event_id: "event-2",
                market_question: "Will CPI rise in April?",
                market_slug: "will-cpi-rise-april",
                market_active: true,
                market_closed: false,
                signal_type: "volume_spike",
                signal_strength: 3.4,
                detected_at: "2026-03-18T12:05:00Z",
                summary: "Volume jumped versus baseline",
                metadata: { summary: "Volume jumped versus baseline" },
              },
            ],
            limit: 10,
            count: 1,
          }),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/signals?")) {
      return Promise.resolve(
        new Response(JSON.stringify(overrides?.signals ?? signalsResponse), { status: 200 }),
      );
    }
    if (url.includes("/runs?")) {
      return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
    }
    if (url.includes("/whale-alerts")) {
      return Promise.resolve(new Response(JSON.stringify(whaleResponse), { status: 200 }));
    }

    return Promise.reject(new Error(`Unhandled fetch: ${url}`));
  });

  vi.stubGlobal("fetch", mockFetch);
  return mockFetch;
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders fetched data and selected market detail", async () => {
    installFetchMock();

    render(<App />);

    expect(
      screen.getByText("Prediction Market Intelligence Dashboard"),
    ).toBeInTheDocument();

    await screen.findByText("Will the Fed cut rates in June?");
    expect(screen.getByText("Price moved 20%")).toBeInTheDocument();
    expect(screen.getByText("Will CPI rise in April?")).toBeInTheDocument();
    expect(screen.getByText("System Status")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Latest run duration")).toBeInTheDocument();
    expect(
      screen.getByText("Trade ingestion is not active yet; whale alerts are deferred."),
    ).toBeInTheDocument();
  });

  it("clicking a signal selects that market and updates the detail panel", async () => {
    installFetchMock();

    render(<App />);

    await screen.findByText("Will CPI rise in April?");

    fireEvent.click(screen.getByRole("button", { name: /Will CPI rise in April\?/i }));

    await screen.findAllByText("Will CPI rise in April?");
    expect(screen.getByText("Inflation market")).toBeInTheDocument();
    expect(screen.getByText("Volume jumped versus baseline")).toBeInTheDocument();
  });

  it("surfaces stronger signals first in the global feed", async () => {
    installFetchMock();

    render(<App />);

    const panel = await screen.findByText("Interesting Right Now");
    const signalContainer = panel.closest(".panel");
    expect(signalContainer).not.toBeNull();
    const titles = within(signalContainer as HTMLElement).getAllByText(/Will .* in .*\?/i);
    expect(titles[0]).toHaveTextContent("Will CPI rise in April?");
  });

  it("updates search input and refetches market list", async () => {
    const fetchMock = installFetchMock();

    render(<App />);
    await screen.findByText("Will the Fed cut rates in June?");

    fireEvent.change(screen.getByLabelText("Search markets"), {
      target: { value: "rates" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/markets?limit=20&offset=0&q=rates"),
      );
    });
  });

  it("renders empty chart and signal states when market detail has no history", async () => {
    installFetchMock({
      history: { market_id: "market-1", items: [], count: 0 },
      signals: { items: [], limit: 10, count: 0 },
    });

    render(<App />);

    await screen.findByText("Will the Fed cut rates in June?");
    expect(screen.getByText("No history yet for this market.")).toBeInTheDocument();
    expect(screen.getByText("No recent signals for this market.")).toBeInTheDocument();
  });

  it("renders error state when market fetch fails", async () => {
    installFetchMock({ marketsStatus: 500 });

    render(<App />);

    await screen.findByText("Unable to load markets right now.");
    expect(screen.getByText("Unable to load markets right now.")).toBeInTheDocument();
  });

  it("renders a friendly empty state when no pipeline runs exist", async () => {
    const mockFetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/health")) {
        return Promise.resolve(new Response(JSON.stringify(healthResponse), { status: 200 }));
      }
      if (url.includes("/markets?")) {
        return Promise.resolve(new Response(JSON.stringify(marketsResponse), { status: 200 }));
      }
      if (url.endsWith("/markets/market-1")) {
        return Promise.resolve(new Response(JSON.stringify(marketDetailResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-1/history")) {
        return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-1/signals")) {
        return Promise.resolve(new Response(JSON.stringify(signalsResponse), { status: 200 }));
      }
      if (url.includes("/signals?")) {
        return Promise.resolve(new Response(JSON.stringify(signalsResponse), { status: 200 }));
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], limit: 6, count: 0 }), { status: 200 }),
        );
      }
      if (url.includes("/whale-alerts")) {
        return Promise.resolve(new Response(JSON.stringify(whaleResponse), { status: 200 }));
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);

    await screen.findByText("No ingestion runs recorded yet. Start the pipeline to populate status metrics and freshness data.");
    expect(screen.getByText("No ingestion runs recorded yet. Start the pipeline to populate status metrics and freshness data.")).toBeInTheDocument();
  });
});
