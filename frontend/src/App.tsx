import { useEffect, useMemo, useState } from "react";

import { getHealth, getMarkets, getRuns, getSignals } from "./api/client";
import { MarketDetail } from "./components/MarketDetail";
import { MarketList } from "./components/MarketList";
import { RunsPanel } from "./components/RunsPanel";
import { SearchControls } from "./components/SearchControls";
import { SignalList } from "./components/SignalList";
import type { HealthResponse, MarketSummary, RunItem, SignalItem } from "./types";

const PAGE_SIZE = 20;

type ActiveFilter = "all" | "active" | "closed";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");

  const [markets, setMarkets] = useState<MarketSummary[]>([]);
  const [marketsLoading, setMarketsLoading] = useState(true);
  const [marketsError, setMarketsError] = useState<string | null>(null);
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [signalsError, setSignalsError] = useState<string | null>(null);

  const [runs, setRuns] = useState<RunItem[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [runsError, setRunsError] = useState<string | null>(null);

  const marketParams = useMemo(() => {
    const active = activeFilter === "active" ? true : undefined;
    const closed = activeFilter === "closed" ? true : undefined;

    return {
      limit: PAGE_SIZE,
      offset: 0,
      q: query.trim() || undefined,
      active,
      closed,
    };
  }, [activeFilter, query]);

  useEffect(() => {
    let active = true;

    getHealth()
      .then((response) => {
        if (!active) {
          return;
        }
        setHealth(response);
        setHealthError(null);
      })
      .catch(() => {
        if (active) {
          setHealthError("Backend unavailable");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setMarketsLoading(true);
    setMarketsError(null);

    getMarkets(marketParams)
      .then((response) => {
        if (!active) {
          return;
        }

        setMarkets(response.items);
        setOffset(response.items.length);
        setHasMore(response.count === PAGE_SIZE);
        setSelectedMarketId((current) => {
          if (response.items.length === 0) {
            return null;
          }

          const currentStillVisible = response.items.some(
            (market) => market.market_id === current,
          );
          return currentStillVisible ? current : response.items[0].market_id;
        });
      })
      .catch(() => {
        if (active) {
          setMarketsError("Unable to load markets right now.");
          setMarkets([]);
          setHasMore(false);
        }
      })
      .finally(() => {
        if (active) {
          setMarketsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [marketParams]);

  useEffect(() => {
    let active = true;

    getSignals({ limit: 8 })
      .then((response) => {
        if (!active) {
          return;
        }
        setSignals(response.items);
        setSignalsError(null);
      })
      .catch(() => {
        if (active) {
          setSignals([]);
          setSignalsError("Unable to load recent signals.");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setRunsLoading(true);

    getRuns({ limit: 6 })
      .then((response) => {
        if (!active) {
          return;
        }
        setRuns(response.items);
        setRunsError(null);
      })
      .catch(() => {
        if (active) {
          setRuns([]);
          setRunsError("Unable to load recent pipeline runs.");
        }
      })
      .finally(() => {
        if (active) {
          setRunsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  function handleLoadMore() {
    const active = activeFilter === "active" ? true : undefined;
    const closed = activeFilter === "closed" ? true : undefined;

    getMarkets({
      limit: PAGE_SIZE,
      offset,
      q: query.trim() || undefined,
      active,
      closed,
    })
      .then((response) => {
        setMarkets((current) => [...current, ...response.items]);
        setOffset((current) => current + response.items.length);
        setHasMore(response.count === PAGE_SIZE);
      })
      .catch(() => {
        setMarketsError("Unable to load more markets right now.");
      });
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Information Edge</p>
          <h1>Prediction Market Intelligence Dashboard</h1>
          <p className="app-subtitle">
            Browse live markets, inspect historical probability movement, and
            surface rule-based signals from the automated pipeline.
          </p>
        </div>
        <div className="health-badge">
          <span>{healthError ? healthError : health?.status ?? "Checking backend"}</span>
          <small>{health ? `API ${health.version}` : "FastAPI read layer"}</small>
        </div>
      </header>

      <main className="dashboard-layout">
        <aside className="sidebar-column">
          <SearchControls
            query={query}
            activeFilter={activeFilter}
            onQueryChange={setQuery}
            onActiveFilterChange={setActiveFilter}
          />
          <MarketList
            markets={markets}
            selectedMarketId={selectedMarketId}
            onSelectMarket={setSelectedMarketId}
            loading={marketsLoading}
            error={marketsError}
            onLoadMore={handleLoadMore}
            hasMore={hasMore}
          />
        </aside>

        <section className="content-column">
          <div className="top-grid">
            <SignalList
              signals={signals}
              title="Interesting Right Now"
              emptyMessage={signalsError ?? "No recent signals across markets."}
            />
            <RunsPanel runs={runs} loading={runsLoading} error={runsError} />
          </div>
          <MarketDetail marketId={selectedMarketId} />
        </section>
      </main>
    </div>
  );
}
