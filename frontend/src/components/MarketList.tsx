import type { MarketSummary } from "../types";

type MarketListProps = {
  markets: MarketSummary[];
  selectedMarketId: string | null;
  onSelectMarket: (marketId: string) => void;
  loading: boolean;
  error: string | null;
  onLoadMore: () => void;
  hasMore: boolean;
};

function formatNumber(value: number | null) {
  if (value === null) {
    return "--";
  }

  return value.toFixed(2);
}

function formatDate(value: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString();
}

export function MarketList({
  markets,
  selectedMarketId,
  onSelectMarket,
  loading,
  error,
  onLoadMore,
  hasMore,
}: MarketListProps) {
  if (loading) {
    return <div className="panel list-state">Loading markets...</div>;
  }

  if (error) {
    return <div className="panel list-state error-state">{error}</div>;
  }

  if (markets.length === 0) {
    return <div className="panel list-state">No markets found for the current filters.</div>;
  }

  return (
    <div className="panel market-list-panel">
      <ul className="market-list" aria-label="Market list">
        {markets.map((market) => (
          <li key={market.market_id}>
            <button
              className={
                selectedMarketId === market.market_id
                  ? "market-row selected"
                  : "market-row"
              }
              onClick={() => onSelectMarket(market.market_id)}
              type="button"
            >
              <div className="market-row-main">
                <span className="market-question">
                  {market.question ?? market.slug ?? market.market_id}
                </span>
                <span
                  className={
                    market.closed
                      ? "status-badge closed"
                      : "status-badge active"
                  }
                >
                  {market.closed ? "Closed" : market.active ? "Active" : "Unknown"}
                </span>
              </div>
              <div className="market-row-meta">
                <span>Price {formatNumber(market.latest_price)}</span>
                <span>Volume {formatNumber(market.latest_volume)}</span>
                <span>{formatDate(market.latest_snapshot_at)}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>

      {hasMore ? (
        <button className="load-more-button" onClick={onLoadMore} type="button">
          Load more
        </button>
      ) : null}
    </div>
  );
}
