type SearchControlsProps = {
  query: string;
  activeFilter: "all" | "active" | "closed";
  category: string;
  categories: string[];
  hasSignalsOnly: boolean;
  signalType: string;
  onQueryChange: (value: string) => void;
  onActiveFilterChange: (value: "all" | "active" | "closed") => void;
  onCategoryChange: (value: string) => void;
  onHasSignalsOnlyChange: (value: boolean) => void;
  onSignalTypeChange: (value: string) => void;
};

export function SearchControls({
  query,
  activeFilter,
  category,
  categories,
  hasSignalsOnly,
  signalType,
  onQueryChange,
  onActiveFilterChange,
  onCategoryChange,
  onHasSignalsOnlyChange,
  onSignalTypeChange,
}: SearchControlsProps) {
  return (
    <div className="panel search-panel">
      <div className="panel-header">
        <h2>Market Browser</h2>
        <p>Search prediction markets and focus on the contracts that matter right now.</p>
      </div>
      <label className="field">
        <span>Keyword search</span>
        <input
          aria-label="Search markets"
          type="search"
          value={query}
          placeholder="Search by question or slug"
          onChange={(event) => onQueryChange(event.target.value)}
        />
      </label>
      <div className="filter-grid">
        <label className="field">
          <span>Category</span>
          <select
            aria-label="Category filter"
            value={category}
            onChange={(event) => onCategoryChange(event.target.value)}
          >
            <option value="all">All</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Signal type</span>
          <select
            aria-label="Signal type filter"
            value={signalType}
            onChange={(event) => onSignalTypeChange(event.target.value)}
          >
            <option value="all">All</option>
            <option value="price_movement">price_movement</option>
            <option value="volume_spike">volume_spike</option>
            <option value="liquidity_shift">liquidity_shift</option>
            <option value="whale">whale</option>
          </select>
        </label>
      </div>
      <label className="toggle-row">
        <input
          aria-label="With signals only"
          type="checkbox"
          checked={hasSignalsOnly}
          onChange={(event) => onHasSignalsOnlyChange(event.target.checked)}
        />
        <span>With signals only</span>
      </label>
      <div className="filter-row" role="group" aria-label="Market status filter">
        <button
          className={activeFilter === "all" ? "chip chip-active" : "chip"}
          onClick={() => onActiveFilterChange("all")}
          type="button"
        >
          All
        </button>
        <button
          className={activeFilter === "active" ? "chip chip-active" : "chip"}
          onClick={() => onActiveFilterChange("active")}
          type="button"
        >
          Active
        </button>
        <button
          className={activeFilter === "closed" ? "chip chip-active" : "chip"}
          onClick={() => onActiveFilterChange("closed")}
          type="button"
        >
          Closed
        </button>
      </div>
    </div>
  );
}
