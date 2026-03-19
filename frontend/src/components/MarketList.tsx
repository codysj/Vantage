import type { MarketSummary } from "../types";
import {
  formatCompactNumber,
  formatProbability,
  formatRelativeTime,
} from "../utils/format";

type MarketListProps = {
  markets: MarketSummary[];
  selectedMarketId: string | null;
  onSelectMarket: (marketId: string) => void;
  loading: boolean;
  error: string | null;
  onLoadMore: () => void;
  hasMore: boolean;
};

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
    return <div className="panel list-state">No markets match the current filters.</div>;
  }

  return (
    <div className="panel market-list-panel">
      <ul className="market-list" aria-label="Market list">
        {markets.map((market) => (
          <li key={market.market_id}>
            <button
              className={
                selectedMarketId === market.market_id
                  ? "market-row selected market-row-selected-strong"
                  : "market-row"
              }
              onClick={() => onSelectMarket(market.market_id)}
              type="button"
            >
              <div className="market-row-main">
                <span className="market-question">
                  {market.question ?? market.slug ?? market.market_id}
                </span>
                <div className="market-row-badges">
                  {market.category ? (
                    <span className="market-category-badge">{market.category}</span>
                  ) : null}
                  {market.has_signals ? (
                    <span className="signal-presence-badge">Signals</span>
                  ) : null}
                  {market.has_whales ? (
                    <span className="whale-presence-badge">Whales</span>
                  ) : null}
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
              </div>
              <div className="market-row-meta">
                <span>Price {formatProbability(market.latest_price)}</span>
                <span>Volume {formatCompactNumber(market.latest_volume)}</span>
                <span title={market.latest_snapshot_at ?? undefined}>
                  {formatRelativeTime(market.latest_snapshot_at)}
                </span>
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
