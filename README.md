# Information Edge Phase 7: Sentiment Overlay

This repo now covers Phase 1 through Phase 7 of Information Edge plus the whale tracker: it can fetch Polymarket events and trades, store and analyze them, run a repeatable ingestion pipeline, generate signals and whale events, expose market analytics through a read-only FastAPI backend, render a React dashboard on top of that backend, enrich markets with on-demand cached news sentiment, and visualize price, sentiment, and market events together in one correlation view.

## What The Current Version Adds

- A new `frontend/` app built with Vite + React + TypeScript
- A split-panel dashboard with a market browser and market detail view
- Historical price charting with Recharts
- Signal history surfaced in the UI
- Real whale detection from Polymarket trade ingestion
- Whale events persisted and exposed through the API
- Whale activity surfaced in the dashboard and market detail view
- A compact pipeline/system status panel
- On-demand cached market sentiment from recent headlines
- A full market correlation view showing price, sentiment, and anomaly/whale timing together
- Layer toggles, event markers, shared chart tooltips, and recent sentiment headlines in the market detail experience
- Frontend smoke/integration tests with Vitest + React Testing Library

## What Still Does Not Include

- Docker or deployment tooling
- CI/CD automation
- Alerting or notification integrations
- Real-time streaming
- Rich topic clustering or multi-market sentiment analytics

## Schema Overview

### `events`
Stores the outer Polymarket event object. This is where static or slowly changing metadata lives: title, slug, description, question, lifecycle booleans, and API timestamps.

### `markets`
Stores each nested contract/market under an event. This keeps descriptive market metadata separate from changing prices and volumes.

### `market_snapshots`
Stores the time-series part of the pipeline. Any values that can change over time, like last trade price, bid/ask, liquidity, open interest, and volume, go here instead of only living on the `markets` row.

This separation matters because one market can have many historical observations. If we stored changing fields directly on `markets`, we would lose history on every re-run.

### `market_outcomes`
Normalizes stringified fields like `outcomes`, `outcomePrices`, `clobTokenIds`, and `umaResolutionStatuses` into one row per outcome. This keeps binary markets simple now while leaving room for multi-outcome markets later.

### `tags` and `event_tags`
Stores event-level tags when the payload includes them cleanly.

### `trades`
Stores normalized trade data from Polymarket's public Data API `/trades`, keyed back to stored markets through `conditionId`. This is the raw trade history used for whale detection.

### `ingestion_runs`
Stores one row per ingestion cycle. This is the Phase 2 observability table that records when each run started and finished, whether it succeeded, how many records were fetched and written, how many were skipped, and whether integrity checks failed.

### `signals`
Stores the structured outputs of the new Phase 3 analytics layer. Each row represents one explainable event that the system detected from market snapshots, linked back to the triggering market, event, and snapshot.

### `whale_events`
Stores unusually large trades detected relative to a market's own recent trade-size baseline. Each whale event links to the triggering trade and stores the baseline statistics, detection score, and structured metadata used by the API and UI.

### `sentiment_documents`
Stores deduplicated headline/snippet documents fetched on demand for one market.

### `sentiment_scores`
Stores per-document sentiment outputs for the configured HuggingFace model.

### `market_sentiment_summary`
Stores the cached market-level aggregate sentiment summary and last computed time used by the TTL cache.

## Deduplication Strategy

- `events.event_id` is unique, so re-running ingestion updates the same event row instead of creating duplicates.
- `markets.market_id` is unique, so market metadata is updated in place.
- `market_outcomes (market_id, outcome_index)` is unique, so repeated runs update existing outcomes.
- `event_tags (event_id, tag_id)` is unique, so repeated tagging does not duplicate joins.
- `market_snapshots.snapshot_key` is unique, which is the main historical dedupe rule.

Snapshot dedupe works like this:

- If the market payload exposes a source `updatedAt`, the snapshot key is `market_id + source_updated_at`.
- If not, the snapshot key falls back to a hash of stable dynamic fields like price, bid/ask, liquidity, volume, and outcome prices.

This means retries or overlapping pulls do not create duplicate historical rows, while real changes still create new snapshots.

## Project Layout

```text
src/
  api.py
  api_schemas.py
  api_client.py
  config.py
  db.py
  ingest.py
  models.py
  normalize.py
  pipeline.py
  queries.py
  signals.py
migrations/
tests/
frontend/
  src/
  package.json
  vite.config.ts
.env.example
alembic.ini
```

## Setup

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

### 4. Create a PostgreSQL database

Create a database named `information_edge`, or adjust `DATABASE_URL` in `.env`.

### 5. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Then edit `.env` if your local PostgreSQL username, password, host, or database name differs.

Create the frontend env file too:

```powershell
Copy-Item frontend\.env.example frontend\.env
```

### 6. Run the schema migration

```powershell
alembic upgrade head
```

## Running One Ingestion Cycle

Phase 1-compatible entrypoint:

```powershell
python -m src.ingest
```

Phase 2 pipeline entrypoint:

```powershell
python -m src.pipeline once
```

After a successful ingestion cycle, the pipeline now also computes and stores signals for markets touched in that run.
It also fetches recent trades for touched markets, stores them idempotently, and detects whale events from the newly inserted trades.

## Running The API

Start the FastAPI backend locally:

```powershell
uvicorn src.api:app --reload
```

Then open:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

The backend now includes CORS support for the local Vite dev server. By default:

- `http://127.0.0.1:5173`
- `http://localhost:5173`

If your frontend runs from a different origin, update `API_CORS_ORIGINS` in `.env`.

Sentiment requires a GNews API key:

```text
GNEWS_API_KEY=your_key_here
```

## Running The Frontend

Start the React dashboard from the `frontend/` directory:

```powershell
cd frontend
npm run dev
```

Then open the Vite URL shown in the terminal, usually:

- [http://127.0.0.1:5173](http://127.0.0.1:5173)

The frontend reads its backend URL from `frontend/.env`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Make sure the FastAPI backend is running before starting the dashboard if you want live data.

## Running The Continuous Pipeline

Start the local scheduler service:

```powershell
python -m src.pipeline serve
```

The scheduler runs one ingestion cycle every `PIPELINE_INTERVAL_SECONDS` seconds. It is configured to avoid overlapping runs:

- APScheduler runs with `max_instances=1`
- scheduled jobs are coalesced if the process falls behind
- the service also uses an in-process lock and skips a cycle if one is already active

Use `Ctrl+C` to stop the foreground service cleanly.

## Querying Stored Data

List all markets:

```powershell
python -m src.queries list-markets
```

Inspect one market by API id:

```powershell
python -m src.queries market --market-id <MARKET_ID>
```

Inspect one market by slug:

```powershell
python -m src.queries market --slug <MARKET_SLUG>
```

Show stored historical snapshots for one market:

```powershell
python -m src.queries history --market-id <MARKET_ID>
```

Show recent top-volume markets from stored snapshots:

```powershell
python -m src.queries top-volume --limit 10
```

Show events with nested market counts:

```powershell
python -m src.queries events
```

Inspect recent ingestion runs:

```powershell
python -m src.queries runs --limit 10
python -m src.pipeline runs --limit 10
```

Inspect recent signals:

```powershell
python -m src.queries signals --limit 10
python -m src.queries signals --limit 10 --signal-type price_movement
python -m src.queries signals --limit 10 --market-id <MARKET_ID>
```

## API Endpoints

Core read endpoints now include:

- `GET /health`
- `GET /markets`
- `GET /markets/{market_id}`
- `GET /markets/{market_id}/history`
- `GET /markets/{market_id}/signals`
- `GET /markets/{market_id}/sentiment`
- `GET /markets/{market_id}/sentiment/documents`
- `GET /signals`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /whales/recent`
- `GET /markets/{market_id}/whales`
- `GET /markets/{market_id}/whale-summary`
- `GET /whale-alerts`

Useful example requests:

```powershell
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/markets?limit=10&active=true"
curl http://127.0.0.1:8000/markets/market-1
curl http://127.0.0.1:8000/markets/market-1/history
curl http://127.0.0.1:8000/markets/market-1/sentiment
curl http://127.0.0.1:8000/markets/market-1/sentiment/documents
curl "http://127.0.0.1:8000/signals?signal_type=price_movement"
curl "http://127.0.0.1:8000/signals?signal_type=whale"
curl http://127.0.0.1:8000/whales/recent
curl http://127.0.0.1:8000/markets/market-1/whales
curl http://127.0.0.1:8000/markets/market-1/whale-summary
curl http://127.0.0.1:8000/runs
curl http://127.0.0.1:8000/whale-alerts
```

These same endpoints are easy to inspect in a browser or test in Postman.

## Frontend Dashboard

The new dashboard is intentionally simple and read-only:

- left column: search/filter controls and market browser
- upper content area: global signal feed and system status
- lower content area: selected market detail with a full correlation view

The market detail view shows:

- market question and summary stats
- a correlation panel that aligns price history, sentiment trend, and anomaly/whale markers on one timeline
- recent market-specific signals from `/markets/{market_id}/signals`
- cached sentiment summary and recent sentiment headlines from `/markets/{market_id}/sentiment` and `/markets/{market_id}/sentiment/documents`
- an on-demand fallback CTA that generates sentiment context only when a market does not have cached sentiment yet

This gives the project a usable full-stack demo surface for the core product question: whether sentiment shifts and whale/anomaly activity lead, lag, or coincide with market price movement.

## Manual Demo Flow

1. Run PostgreSQL locally and apply migrations.
2. Start the backend with `uvicorn src.api:app --reload`.
3. Start the scheduler or run one ingestion cycle:
   - `python -m src.pipeline once`
   - or `python -m src.pipeline serve`
4. Start the frontend:
   - `cd frontend`
   - `npm run dev`
5. Open the dashboard in your browser.
6. Search for a market, click it, and inspect the correlation view, recent signals, and system status panel.
7. If a market has no cached sentiment yet, click `Load sentiment drivers` in the correlation view to generate and cache it on demand.

## Logging And Integrity Checks

The Phase 2 pipeline logs:

- pipeline startup and shutdown
- scheduler configuration
- start and end of each run
- fetched counts
- inserted or deduplicated snapshot behavior through run counters
- skipped bad records
- integrity-check results
- failures and run duration

Integrity checks are real pipeline steps, not TODOs:

- pre-write checks validate required IDs, numeric parsing, parent-child relationships, negative nonsensical values, and out-of-range probability-like prices
- post-write checks verify duplicate protections, orphan detection, blank critical identifiers, and general DB sanity after each run

Bad individual records are logged and skipped. Systemic post-write failures mark the whole run as failed.

## Signal Detection

Signals are intentionally simple and rule-based in Phase 3:

- `price_movement`: latest price changed sharply versus the earliest snapshot in the lookback window
- `volume_spike`: latest volume is much larger than the recent baseline average
- `liquidity_shift`: latest liquidity changed sharply versus the earliest snapshot in the lookback window

Signals are generated from stored `market_snapshots`, not external APIs. They are deduplicated by `(market_id, signal_type, snapshot_id)` so reruns do not spam duplicate rows for the same triggering snapshot.

## Whale Detection

Whale detection is now a real pipeline stage driven by stored trades from Polymarket's public `/trades` endpoint.

- trade size is normalized as `price * size`
- each market uses its own recent trade history as the baseline
- a whale requires at least `WHALE_MIN_HISTORY_COUNT` prior trades
- the detector computes mean, median, std, median-multiple, and z-score
- a trade is flagged when it clears the absolute minimum notional and exceeds either the z-score or median-multiple threshold

Whale events are stored in `whale_events`, deduplicated by `(trade_id, detection_method)`, and exposed both through whale-specific endpoints and the existing signal feed.

Backfill stored trades into whale events with:

```powershell
python -m src.whales backfill
python -m src.whales backfill --market-id <MARKET_ID>
```

## Sentiment Layer

Sentiment is an on-demand enrichment layer, not part of the scheduled ingestion pipeline.

- the market detail view does one lightweight cached read on market open
- the backend checks `market_sentiment_summary`
- if the cached summary is still within `SENTIMENT_TTL_HOURS`, it returns immediately
- if no sentiment is cached yet, the correlation panel shows a CTA to load sentiment drivers on demand
- clicking that CTA reuses the existing sentiment endpoint to fetch recent GNews headlines, deduplicate documents by URL, score only unscored docs for the configured model, update the summary, and cache the result

This keeps repeat access fast without adding another background worker, while still allowing uncached markets to be enriched from the UI.

## Backend API Design

The FastAPI layer is intentionally thin:

- route handlers stay read-only
- SQLAlchemy sessions are injected with one simple dependency
- the existing query layer is reused and lightly extended for API list/detail shapes
- Pydantic response schemas keep JSON clean and frontend-friendly

## Running Tests

```powershell
.\venv\Scripts\python.exe -m pytest
```

This includes the Python backend suite for ingestion, pipeline, signals, queries, and API behavior.

Frontend tests run separately:

```powershell
cd frontend
npm run test
```

The frontend test suite covers the app shell, market list rendering, search-driven refetch behavior, market detail loading, correlation view rendering, empty sentiment CTA behavior, sentiment generation fallback, signal rendering, and fetch failure states.

## Configuration

Environment variables now include:

- `DATABASE_URL`
- `POLYMARKET_BASE_URL`
- `POLYMARKET_EVENTS_PATH`
- `POLYMARKET_TRADES_BASE_URL`
- `POLYMARKET_TRADES_PATH`
- `POLYMARKET_ACTIVE`
- `POLYMARKET_CLOSED`
- `POLYMARKET_LIMIT`
- `POLYMARKET_TRADES_LIMIT`
- `POLYMARKET_TRADES_BATCH_SIZE`
- `POLYMARKET_TIMEOUT_SECONDS`
- `PIPELINE_INTERVAL_SECONDS`
- `PIPELINE_LOG_LEVEL`
- `PIPELINE_LOG_TO_FILE`
- `PIPELINE_LOG_FILE`
- `PIPELINE_MAX_RETRIES`
- `PIPELINE_MISFIRE_GRACE_SECONDS`
- `PIPELINE_CONTINUOUS_DEFAULT`
- `SIGNAL_PRICE_THRESHOLD`
- `SIGNAL_VOLUME_MULTIPLIER`
- `SIGNAL_LIQUIDITY_THRESHOLD`
- `SIGNAL_LOOKBACK_WINDOW_MINUTES`
- `WHALE_MIN_HISTORY_COUNT`
- `WHALE_BASELINE_TRADE_COUNT`
- `WHALE_ZSCORE_THRESHOLD`
- `WHALE_MEDIAN_MULTIPLIER_THRESHOLD`
- `WHALE_ABSOLUTE_MIN_NOTIONAL`
- `GNEWS_API_KEY`
- `GNEWS_BASE_URL`
- `GNEWS_SEARCH_PATH`
- `SENTIMENT_TTL_HOURS`
- `SENTIMENT_MAX_DOCS_PER_MARKET`
- `SENTIMENT_MODEL_NAME`
- `SENTIMENT_REQUEST_TIMEOUT_SECONDS`

## Design Notes

- PostgreSQL is the default and primary target for this phase.
- Tests use in-memory SQLite for speed, but the production path remains PostgreSQL plus Alembic.
- Raw event and market payloads are stored so future phases can add fields without guessing how older payloads looked.
- The code favors small helper functions and explicit data flow over framework-heavy abstractions.
- Scheduling is intentionally in-process and lightweight so the pipeline stays easy to explain in an interview.
- Signal detection is also intentionally lightweight: clear thresholds, recent-vs-baseline comparisons, and explainable metadata instead of heavier statistical or ML models.
- Sentiment uses lazy caching by design so markets are enriched only when needed, and repeated reads stay fast.
- The backend API is read-only by design in this phase, so it stays focused on exposing the analytics system rather than becoming a full admin platform.
- The frontend is also intentionally simple: plain `fetch`, one main dashboard view, lightweight CSS, and Recharts for a synchronized correlation view instead of a heavier analytics frontend.

## Known Limitation

The pipeline now ingests events plus recent public trades, but it still relies on Polymarket's read APIs rather than authenticated order/trader infrastructure. Sentiment uses headline/snippet text only, requires a configured GNews API key, and remains a lightweight market-level enrichment layer rather than a full news intelligence system. Auth, deployment, real-time streaming, and production infra remain deferred to later phases.
