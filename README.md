# Information Edge Phase 1: Data Storage

This repo now covers Phase 1 of Information Edge: fetch active Polymarket events, normalize messy API payloads, store durable event and market metadata in PostgreSQL, and append deduplicated historical market snapshots for later analysis.

## What Phase 1 Includes

- A PostgreSQL-first relational schema with Alembic migrations
- A normalization layer for Polymarket payload quirks
- One-shot ingestion that upserts events, markets, outcomes, and event tags
- Historical `market_snapshots` storage for time-series queries
- A small query helper CLI for inspecting stored data
- Tests for normalization, deduplication, and query behavior

## What Phase 1 Does Not Include

- Scheduling or recurring ingestion
- Signal detection
- FastAPI endpoints
- Frontend/dashboard work
- Docker or deployment tooling
- CI/CD automation

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

## Running Ingestion

Fetch and store one batch of Polymarket events:

```powershell
python -m src.ingest
```

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

## Running Tests

```powershell
pytest
```

## Design Notes

- PostgreSQL is the default and primary target for this phase.
- Tests use in-memory SQLite for speed, but the production path remains PostgreSQL plus Alembic.
- Raw event and market payloads are stored so future phases can add fields without guessing how older payloads looked.
- The code favors small helper functions and explicit data flow over framework-heavy abstractions.

## Known Limitation

The current Phase 1 ingestion command only uses Gamma `/events`. Polymarket exposes separate trade-oriented APIs, but this repo does not ingest them yet. The `trades` table is included so Phase 2 or a later storage extension can add real trade history without redesigning the rest of the schema.
