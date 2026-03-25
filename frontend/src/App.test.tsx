import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./components/PriceChart", () => ({
  PriceChart: ({ history }: { history: Array<unknown> }) => (
    <div data-testid="price-chart-mock">History points: {history.length}</div>
  ),
}));

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
      category: "Economy",
      has_signals: true,
      has_whales: true,
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
      category: "Economy",
      has_signals: false,
      has_whales: false,
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
  available_categories: ["Economy", "Politics"],
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

const marketSignalsResponse = {
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
      id: 101,
      market_id: "market-1",
      event_id: "event-1",
      market_question: "Will the Fed cut rates in June?",
      market_slug: "will-fed-cut-rates-june",
      market_active: true,
      market_closed: false,
      signal_type: "whale",
      signal_strength: 10,
      detected_at: "2026-03-18T12:01:00Z",
      summary: "Whale trade 8.27x median notional",
      metadata: { summary: "Whale trade 8.27x median notional" },
    },
  ],
  limit: 10,
  count: 2,
};

const globalSignalsResponse = {
  items: [
    {
      id: 101,
      market_id: "market-1",
      event_id: "event-1",
      market_question: "Will the Fed cut rates in June?",
      market_slug: "will-fed-cut-rates-june",
      market_active: true,
      market_closed: false,
      signal_type: "whale",
      signal_strength: 10,
      detected_at: "2026-03-18T12:01:00Z",
      summary: "Whale trade 8.27x median notional",
      metadata: { summary: "Whale trade 8.27x median notional" },
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

const marketWhalesResponse = {
  items: [
    {
      id: 1,
      market_id: "market-1",
      event_id: "event-1",
      market_question: "Will the Fed cut rates in June?",
      market_slug: "will-fed-cut-rates-june",
      detected_at: "2026-03-18T12:01:00Z",
      trade_size: 620,
      whale_score: 10,
      median_multiple: 8.27,
      side: "BUY",
      outcome_label: "Yes",
      proxy_wallet: "0xabc",
      detection_method: "market_local_baseline",
      summary: "Whale trade 8.27x median notional",
      metadata: { summary: "Whale trade 8.27x median notional" },
    },
  ],
  limit: 8,
  count: 1,
};

const secondMarketWhalesResponse = {
  items: [],
  limit: 8,
  count: 0,
};

const whaleSummaryResponse = {
  market_id: "market-1",
  total_whale_events: 1,
  most_recent_whale_at: "2026-03-18T12:01:00Z",
  largest_whale_trade: 620,
  average_whale_score: 10,
  whale_events_24h: 1,
  whale_events_7d: 1,
  has_recent_whale_activity: true,
};

const secondMarketWhaleSummaryResponse = {
  market_id: "market-2",
  total_whale_events: 0,
  most_recent_whale_at: null,
  largest_whale_trade: null,
  average_whale_score: null,
  whale_events_24h: 0,
  whale_events_7d: 0,
  has_recent_whale_activity: false,
};

const sentimentSummaryResponse = {
  market_id: "market-1",
  status: "ok",
  message: null,
  avg_sentiment: 0.42,
  doc_count: 2,
  pos_count: 1,
  neg_count: 0,
  neutral_count: 1,
  last_updated: "2026-03-18T12:02:00Z",
};

const secondMarketSentimentSummaryResponse = {
  market_id: "market-2",
  status: "empty",
  message: "No recent headlines found for this market.",
  avg_sentiment: 0,
  doc_count: 0,
  pos_count: 0,
  neg_count: 0,
  neutral_count: 0,
  last_updated: "2026-03-18T12:02:00Z",
};

const sentimentDocumentsResponse = {
  market_id: "market-1",
  status: "ok",
  message: null,
  items: [
    {
      id: 1,
      source_name: "Reuters",
      url: "https://example.com/fed-rates",
      title: "Fed outlook remains in focus",
      snippet: "Markets continue to watch the Fed closely.",
      published_at: "2026-03-18T11:30:00Z",
      sentiment_label: "positive",
      sentiment_confidence: 0.88,
      sentiment_value: 0.88,
    },
  ],
  count: 1,
};

const secondMarketSentimentDocumentsResponse = {
  market_id: "market-2",
  status: "empty",
  message: "No recent headlines found for this market.",
  items: [],
  count: 0,
};

function installFetchMock(overrides?: {
  history?: typeof historyResponse;
  signals?: typeof marketSignalsResponse;
  globalSignals?: typeof globalSignalsResponse;
  marketsStatus?: number;
  runs?: typeof runsResponse;
  marketWhales?: typeof marketWhalesResponse;
  whaleSummary?: typeof whaleSummaryResponse;
  sentimentSummary?: typeof sentimentSummaryResponse;
  sentimentDocuments?: typeof sentimentDocumentsResponse;
}) {
  const mockFetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);

    if (url.includes("/health")) {
      return Promise.resolve(new Response(JSON.stringify(healthResponse), { status: 200 }));
    }
    if (url.includes("/markets?")) {
      const status = overrides?.marketsStatus ?? 200;
      return Promise.resolve(
        new Response(status === 200 ? JSON.stringify(marketsResponse) : "error", { status }),
      );
    }
    if (url.endsWith("/markets/market-1")) {
      return Promise.resolve(new Response(JSON.stringify(marketDetailResponse), { status: 200 }));
    }
    if (url.endsWith("/markets/market-2")) {
      return Promise.resolve(
        new Response(JSON.stringify(secondMarketDetailResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-1/history")) {
      return Promise.resolve(
        new Response(JSON.stringify(overrides?.history ?? historyResponse), { status: 200 }),
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
        new Response(JSON.stringify(overrides?.signals ?? marketSignalsResponse), { status: 200 }),
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
        new Response(
          JSON.stringify(overrides?.globalSignals ?? globalSignalsResponse),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/runs?")) {
      return Promise.resolve(
        new Response(JSON.stringify(overrides?.runs ?? runsResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-1/whales")) {
      return Promise.resolve(
        new Response(
          JSON.stringify(overrides?.marketWhales ?? marketWhalesResponse),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/markets/market-2/whales")) {
      return Promise.resolve(
        new Response(JSON.stringify(secondMarketWhalesResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-1/whale-summary")) {
      return Promise.resolve(
        new Response(
          JSON.stringify(overrides?.whaleSummary ?? whaleSummaryResponse),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/markets/market-2/whale-summary")) {
      return Promise.resolve(
        new Response(JSON.stringify(secondMarketWhaleSummaryResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-1/sentiment/documents")) {
      return Promise.resolve(
        new Response(
          JSON.stringify(overrides?.sentimentDocuments ?? sentimentDocumentsResponse),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/markets/market-2/sentiment/documents")) {
      return Promise.resolve(
        new Response(JSON.stringify(secondMarketSentimentDocumentsResponse), { status: 200 }),
      );
    }
    if (url.includes("/markets/market-1/sentiment")) {
      return Promise.resolve(
        new Response(
          JSON.stringify(overrides?.sentimentSummary ?? sentimentSummaryResponse),
          { status: 200 },
        ),
      );
    }
    if (url.includes("/markets/market-2/sentiment")) {
      return Promise.resolve(
        new Response(JSON.stringify(secondMarketSentimentSummaryResponse), { status: 200 }),
      );
    }

    return Promise.reject(new Error(`Unhandled fetch: ${url}`));
  });

  vi.stubGlobal("fetch", mockFetch);
  return mockFetch;
}

async function findMarketList() {
  return screen.findByLabelText("Market list");
}

async function findMarketButton(name: RegExp) {
  const list = await findMarketList();
  return within(list).findByRole("button", { name });
}

function getMarketButton(list: HTMLElement, name: RegExp) {
  return within(list).getByRole("button", { name });
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders fetched data, system status, and the correlation view", async () => {
    installFetchMock();

    render(<App />);

    expect(screen.getByText("Prediction Market Intelligence Dashboard")).toBeInTheDocument();

    await findMarketButton(/Will the Fed cut rates in June\?/i);
    expect(screen.getByText("System Status")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Correlation View")).toBeInTheDocument();
    expect(screen.getAllByText("Whale trade 8.27x median notional").length).toBeGreaterThan(0);
    expect(await screen.findByText("Recent whales")).toBeInTheDocument();
  });

  it("renders signal and whale badges only on matching markets", async () => {
    installFetchMock();

    render(<App />);

    const list = await findMarketList();
    const signalBadges = within(list).getAllByText("Signals");
    const whaleBadges = within(list).getAllByText("Whales");

    expect(signalBadges).toHaveLength(1);
    expect(whaleBadges).toHaveLength(1);
    expect(getMarketButton(list, /Will the Fed cut rates in June\?/i)).toHaveTextContent("Signals");
    expect(getMarketButton(list, /Will the Fed cut rates in June\?/i)).toHaveTextContent("Whales");
    expect(getMarketButton(list, /Will CPI rise in April\?/i)).not.toHaveTextContent("Signals");
    expect(getMarketButton(list, /Will CPI rise in April\?/i)).not.toHaveTextContent("Whales");
  });

  it("clicking a signal selects that market and updates the detail panel", async () => {
    installFetchMock();

    render(<App />);

    const list = await findMarketList();

    fireEvent.click(getMarketButton(list, /Will CPI rise in April\?/i));

    await screen.findByText("Inflation market");
    expect(screen.getByText("Inflation market")).toBeInTheDocument();
    expect(screen.getByText("Correlation View")).toBeInTheDocument();
  });

  it("surfaces stronger whale signals first in the global feed", async () => {
    installFetchMock();

    render(<App />);

    const panel = await screen.findByText("Interesting Right Now");
    const signalContainer = panel.closest(".panel");
    expect(signalContainer).not.toBeNull();
    const titles = within(signalContainer as HTMLElement).getAllByText(/Will .* in .*\?/i);
    expect(titles[0]).toHaveTextContent("Will the Fed cut rates in June?");
    expect(
      within(signalContainer as HTMLElement).getByText(
        "Trade size stands out relative to this market's recent baseline.",
      ),
    ).toBeInTheDocument();
  });

  it("updates search input and refetches market list", async () => {
    const fetchMock = installFetchMock();

    render(<App />);
    await findMarketButton(/Will the Fed cut rates in June\?/i);

    fireEvent.change(screen.getByLabelText("Search markets"), {
      target: { value: "rates" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/markets?limit=20&offset=0&q=rates"),
      );
    });
  });

  it("applies browser filter controls to the market request", async () => {
    const fetchMock = installFetchMock();

    render(<App />);
    await findMarketButton(/Will the Fed cut rates in June\?/i);

    fireEvent.change(screen.getByLabelText("Category filter"), {
      target: { value: "Economy" },
    });
    fireEvent.click(screen.getByLabelText("With signals only"));
    fireEvent.change(screen.getByLabelText("Signal type filter"), {
      target: { value: "whale" },
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(
          "/markets?limit=20&offset=0&category=Economy&has_signals=true&signal_type=whale",
        ),
      );
    });
  });

  it("with signals only excludes markets without signals", async () => {
    const mockFetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/health")) {
        return Promise.resolve(new Response(JSON.stringify(healthResponse), { status: 200 }));
      }
      if (url.includes("/markets?") && url.includes("has_signals=true")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ...marketsResponse,
              items: [marketsResponse.items[0]],
              count: 1,
            }),
            { status: 200 },
          ),
        );
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
        return Promise.resolve(
          new Response(JSON.stringify(marketSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/signals?")) {
        return Promise.resolve(
          new Response(JSON.stringify(globalSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-1/whales")) {
        return Promise.resolve(
          new Response(JSON.stringify(marketWhalesResponse), { status: 200 }),
        );
      }
      if (url.includes("/markets/market-1/whale-summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(whaleSummaryResponse), { status: 200 }),
        );
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);
    await findMarketButton(/Will the Fed cut rates in June\?/i);

    fireEvent.click(screen.getByLabelText("With signals only"));

    await waitFor(() => {
      const marketList = screen.getByLabelText("Market list");
      expect(
        within(marketList).queryByRole("button", { name: /Will CPI rise in April\?/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("signal type filtering only matches markets with whale activity when whale is selected", async () => {
    const mockFetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/health")) {
        return Promise.resolve(new Response(JSON.stringify(healthResponse), { status: 200 }));
      }
      if (url.includes("/markets?") && url.includes("signal_type=whale")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              ...marketsResponse,
              items: [marketsResponse.items[0]],
              count: 1,
            }),
            { status: 200 },
          ),
        );
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
        return Promise.resolve(
          new Response(JSON.stringify(marketSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/signals?")) {
        return Promise.resolve(
          new Response(JSON.stringify(globalSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-1/whales")) {
        return Promise.resolve(
          new Response(JSON.stringify(marketWhalesResponse), { status: 200 }),
        );
      }
      if (url.includes("/markets/market-1/whale-summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(whaleSummaryResponse), { status: 200 }),
        );
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);
    await findMarketButton(/Will the Fed cut rates in June\?/i);

    fireEvent.change(screen.getByLabelText("Signal type filter"), {
      target: { value: "whale" },
    });

    await waitFor(() => {
      const marketList = screen.getByLabelText("Market list");
      expect(
        within(marketList).queryByRole("button", { name: /Will CPI rise in April\?/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("marks the selected market row clearly in the browser", async () => {
    installFetchMock();

    render(<App />);
    const selectedRow = await findMarketButton(/Will the Fed cut rates in June\?/i);

    expect(selectedRow.className).toContain("market-row-selected-strong");
  });

  it("renders empty chart and signal states when market detail has no history", async () => {
    installFetchMock({
      history: { market_id: "market-1", items: [], count: 0 },
      signals: { items: [], limit: 10, count: 0 },
      marketWhales: { items: [], limit: 8, count: 0 },
      whaleSummary: {
        market_id: "market-1",
        total_whale_events: 0,
        most_recent_whale_at: null,
        largest_whale_trade: null,
        average_whale_score: null,
        whale_events_24h: 0,
        whale_events_7d: 0,
        has_recent_whale_activity: false,
      },
    });

    render(<App />);

    await findMarketButton(/Will the Fed cut rates in June\?/i);
    expect(screen.getByText("No history yet for this market.")).toBeInTheDocument();
    expect(screen.getByText("No recent signals for this market.")).toBeInTheDocument();
  });

  it("loads and renders market sentiment automatically inside the correlation view", async () => {
    const fetchMock = installFetchMock();

    render(<App />);

    await findMarketButton(/Will the Fed cut rates in June\?/i);
    await screen.findByText("Latest sentiment");
    expect(screen.getByText("Fed outlook remains in focus")).toBeInTheDocument();
    expect(screen.getByText(/positive 0.88/i)).toBeInTheDocument();
    const calls = fetchMock.mock.calls.map(([input]) => String(input));
    const summaryIndex = calls.findIndex(
      (url) => url.includes("/markets/market-1/sentiment") && !url.includes("/documents"),
    );
    const documentsIndex = calls.findIndex((url) =>
      url.includes("/markets/market-1/sentiment/documents"),
    );
    expect(summaryIndex).toBeGreaterThan(-1);
    expect(documentsIndex).toBeGreaterThan(summaryIndex);
  });

  it("renders a CTA when no sentiment has been generated yet", async () => {
    installFetchMock();

    render(<App />);

    const list = await findMarketList();
    fireEvent.click(getMarketButton(list, /Will CPI rise in April\?/i));
    await screen.findByText("Inflation market");

    await screen.findByText("No sentiment data available yet for this market.");
    expect(screen.getByRole("button", { name: "Load sentiment drivers" })).toBeInTheDocument();
    expect(screen.queryByText("Unable to load sentiment right now.")).not.toBeInTheDocument();
  });

  it("clicking the CTA generates sentiment and refreshes the correlation panel", async () => {
    let generated = false;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
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
      if (url.endsWith("/markets/market-2")) {
        return Promise.resolve(
          new Response(JSON.stringify(secondMarketDetailResponse), { status: 200 }),
        );
      }
      if (url.includes("/markets/market-1/history")) {
        return Promise.resolve(new Response(JSON.stringify(historyResponse), { status: 200 }));
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
          new Response(JSON.stringify(marketSignalsResponse), { status: 200 }),
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
          new Response(JSON.stringify(globalSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-2/sentiment/documents")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              generated
                ? {
                    market_id: "market-2",
                    status: "ok",
                    message: null,
                    items: [
                      {
                        id: 9,
                        source_name: "Bloomberg",
                        url: "https://example.com/cpi",
                        title: "Inflation expectations rise",
                        snippet: "Fresh macro data is driving inflation chatter.",
                        published_at: "2026-03-18T11:45:00Z",
                        sentiment_label: "negative",
                        sentiment_confidence: 0.77,
                        sentiment_value: -0.77,
                      },
                    ],
                    count: 1,
                  }
                : secondMarketSentimentDocumentsResponse,
            ),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/markets/market-2/sentiment")) {
        const body = generated
          ? {
              market_id: "market-2",
              status: "ok",
              message: null,
              avg_sentiment: -0.77,
              doc_count: 1,
              pos_count: 0,
              neg_count: 1,
              neutral_count: 0,
              last_updated: "2026-03-18T12:02:00Z",
            }
          : secondMarketSentimentSummaryResponse;
        generated = true;
        return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
      }
      if (url.includes("/markets/market-1/sentiment/documents")) {
        return Promise.resolve(
          new Response(JSON.stringify(sentimentDocumentsResponse), { status: 200 }),
        );
      }
      if (url.includes("/markets/market-1/sentiment")) {
        return Promise.resolve(
          new Response(JSON.stringify(sentimentSummaryResponse), { status: 200 }),
        );
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const list = await findMarketList();
    fireEvent.click(getMarketButton(list, /Will CPI rise in April\?/i));
    await screen.findByText("Inflation market");
    fireEvent.click(screen.getByRole("button", { name: "Load sentiment drivers" }));

    await screen.findByText("Inflation expectations rise");
    expect(screen.queryByText("No sentiment data available yet for this market.")).not.toBeInTheDocument();
  });

  it("renders structured sentiment availability errors cleanly", async () => {
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
        return Promise.resolve(
          new Response(JSON.stringify(marketSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/signals?")) {
        return Promise.resolve(
          new Response(JSON.stringify(globalSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-1/whales")) {
        return Promise.resolve(
          new Response(JSON.stringify(marketWhalesResponse), { status: 200 }),
        );
      }
      if (url.includes("/markets/market-1/whale-summary")) {
        return Promise.resolve(
          new Response(JSON.stringify(whaleSummaryResponse), { status: 200 }),
        );
      }
      if (url.includes("/markets/market-1/sentiment")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              detail: {
                code: "sentiment_upstream_unavailable",
                message: "Headline source is temporarily unavailable.",
              },
            }),
            { status: 503 },
          ),
        );
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);

    await findMarketButton(/Will the Fed cut rates in June\?/i);

    await screen.findByText("Headline source is temporarily unavailable.");
    expect(screen.queryByRole("button", { name: "Load sentiment drivers" })).not.toBeInTheDocument();
    expect(screen.queryByText("Unable to load sentiment right now.")).not.toBeInTheDocument();
  });

  it("shows a true config error only for sentiment configuration failures", async () => {
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
        return Promise.resolve(
          new Response(JSON.stringify(marketSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/signals?")) {
        return Promise.resolve(
          new Response(JSON.stringify(globalSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
      }
      if (url.includes("/markets/market-1/sentiment")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              detail: {
                code: "sentiment_config_error",
                message: "Sentiment is not configured yet.",
              },
            }),
            { status: 503 },
          ),
        );
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);

    await findMarketButton(/Will the Fed cut rates in June\?/i);

    await screen.findByText("Sentiment is not configured yet.");
    expect(screen.queryByRole("button", { name: "Load sentiment drivers" })).not.toBeInTheDocument();
  });

  it("layer toggles hide sentiment and whale marker content cleanly", async () => {
    installFetchMock();

    render(<App />);

    await findMarketButton(/Will the Fed cut rates in June\?/i);
    await screen.findByText("Correlation View");

    fireEvent.click(screen.getByRole("button", { name: "Sentiment" }));
    expect(screen.queryByText("Recent Sentiment Headlines")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Whales" }));
    expect(screen.getByRole("button", { name: "Whales" })).toBeInTheDocument();
  });

  it("renders error state when market fetch fails", async () => {
    installFetchMock({ marketsStatus: 500 });

    render(<App />);

    await screen.findByText("Unable to load markets right now.");
  });

  it("renders an empty state when filters produce no markets", async () => {
    const mockFetch = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.includes("/health")) {
        return Promise.resolve(new Response(JSON.stringify(healthResponse), { status: 200 }));
      }
      if (url.includes("/markets?")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [],
              limit: 20,
              offset: 0,
              count: 0,
              available_categories: ["Economy"],
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/signals?")) {
        return Promise.resolve(
          new Response(JSON.stringify(globalSignalsResponse), { status: 200 }),
        );
      }
      if (url.includes("/runs?")) {
        return Promise.resolve(new Response(JSON.stringify(runsResponse), { status: 200 }));
      }

      return Promise.reject(new Error(`Unhandled fetch: ${url}`));
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);

    await screen.findByText("No markets match the current filters.");
  });

  it("renders a friendly empty state when no pipeline runs exist", async () => {
    installFetchMock({
      runs: { items: [], limit: 6, count: 0 },
    });

    render(<App />);

    await screen.findByText(
      "No ingestion runs recorded yet. Start the pipeline to populate status metrics and freshness data.",
    );
  });
});
