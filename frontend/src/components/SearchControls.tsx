type SearchControlsProps = {
  query: string;
  activeFilter: "all" | "active" | "closed";
  onQueryChange: (value: string) => void;
  onActiveFilterChange: (value: "all" | "active" | "closed") => void;
};

export function SearchControls({
  query,
  activeFilter,
  onQueryChange,
  onActiveFilterChange,
}: SearchControlsProps) {
  return (
    <div className="panel search-panel">
      <div className="panel-header">
        <h2>Market Browser</h2>
        <p>Search prediction markets and inspect recent system activity.</p>
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
