# Information Edge Phase 4: Backend API

This repo now covers Phase 1 through Phase 4 of Information Edge: it can fetch Polymarket events, store and analyze them, run a repeatable ingestion pipeline, generate signals, and expose the resulting market analytics through a read-only FastAPI backend.

## What Phase 4 Adds

- A FastAPI app with Swagger docs at `/docs`
- Read-only endpoints for markets, historical snapshots, signals, runs, and whale-alert placeholder responses
- Typed response schemas for clean JSON output
- Automated API tests with FastAPI `TestClient`
- Browser/Postman-friendly local API demo support

## What Still Does Not Include

- Frontend/dashboard work
- Docker or deployment tooling
- CI/CD automation
- Alerting or notification integrations
- Machine learning or statistical modeling
- Real-time streaming

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
This table exists as a Phase 1 placeholder schema only. Trade ingestion is intentionally not active yet because this repo currently ingests from Gamma `/events`, and trade history should be wired deliberately from Polymarket's trade-oriented endpoints in a later phase.

### `ingestion_runs`
Stores one row per ingestion cycle. This is the Phase 2 observability table that records when each run started and finished, whether it succeeded, how many records were fetched and written, how many were skipped, and whether integrity checks failed.

### `signals`
Stores the structured outputs of the new Phase 3 analytics layer. Each row represents one explainable event that the system detected from market snapshots, linked back to the triggering market, event, and snapshot.

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
  api_client.py
  config.py
  db.py
  ingest.py
  models.py
  normalize.py
  queries.py
migrations/
tests/
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

### 3. Create a PostgreSQL database

Create a database named `information_edge`, or adjust `DATABASE_URL` in `.env`.

### 4. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Then edit `.env` if your local PostgreSQL username, password, host, or database name differs.

### 5. Run the schema migration

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

## Running The API

Start the FastAPI backend locally:

```powershell
uvicorn src.api:app --reload
```

Then open:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

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
- `GET /signals`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /whale-alerts`

Useful example requests:

```powershell
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/markets?limit=10&active=true"
curl http://127.0.0.1:8000/markets/market-1
curl http://127.0.0.1:8000/markets/market-1/history
curl "http://127.0.0.1:8000/signals?signal_type=price_movement"
curl http://127.0.0.1:8000/runs
curl http://127.0.0.1:8000/whale-alerts
```

These same endpoints are easy to inspect in a browser or test in Postman.

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

This now includes API tests for health, markets, history, signals, runs, filters, 404 behavior, and whale-alert placeholder responses.

## Configuration

Environment variables now include:

- `DATABASE_URL`
- `POLYMARKET_BASE_URL`
- `POLYMARKET_EVENTS_PATH`
- `POLYMARKET_ACTIVE`
- `POLYMARKET_CLOSED`
- `POLYMARKET_LIMIT`
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

## Design Notes

- PostgreSQL is the default and primary target for this phase.
- Tests use in-memory SQLite for speed, but the production path remains PostgreSQL plus Alembic.
- Raw event and market payloads are stored so future phases can add fields without guessing how older payloads looked.
- The code favors small helper functions and explicit data flow over framework-heavy abstractions.
- Scheduling is intentionally in-process and lightweight so the pipeline stays easy to explain in an interview.
- Signal detection is also intentionally lightweight: clear thresholds, recent-vs-baseline comparisons, and explainable metadata instead of heavier statistical or ML models.
- The backend API is read-only by design in this phase, so it stays focused on exposing the analytics system rather than becoming a full admin platform.

## Known Limitation

The pipeline still ingests only Gamma `/events`. Signals are rule-based and intentionally simple, and whale alerts are currently an honest placeholder because trade ingestion is not active yet. Frontend work, sentiment/NLP, auth, deployment, and production infra remain deferred to later phases.
