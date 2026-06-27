# Hindsight Local Memory

A local-first, air-gap-friendly memory node for agentic systems. The project is designed to run locally with SQLite as the durable source of truth, optional `sqlite-vec` for vector search, and optional FalkorDB Lite as a graph query projection. It is intentionally schema-compatible with a larger Hindsight deployment using PostgreSQL/pgvector and Neo4j.

## Goals

- Local memory for field units, laptops, labs, edge boxes, and disconnected environments.
- Durable append-only sync log for later reconciliation with a master system.
- Deterministic IDs for documents, chunks, entities, claims, embeddings, and graph edges.
- Local vector retrieval through SQLite, with graceful fallback if `sqlite-vec` is unavailable.
- Optional graph projection into FalkorDB Lite.
- Reusable agent and skill specs for other projects.

## Architecture

```text
Field Unit
  SQLite
    documents
    chunks
    embeddings
    entities
    claims
    graph_edges
    sync_events
    tombstones

  Optional sqlite-vec
    vector index tables

  Optional FalkorDB Lite
    graph projection of entities, claims, chunks, and provenance

  Agent Runtime
    ingest -> extract -> embed -> store -> project -> retrieve -> sync bundle
```

## Quick Start

```bash
cd hindsight-local-memory
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python scripts/init_db.py --db ./.hindsight/agent-mem.db
python examples/basic_ingest.py
```

The project works without `sqlite-vec` or FalkorDB installed. Those integrations are isolated behind adapters so you can add them later.

## CLI

```bash
agent-mem init --db ./.hindsight/agent-mem.db
agent-mem ingest --db ./.hindsight/agent-mem.db --text "Calvin is designing a local-first memory system."
agent-mem search --db ./.hindsight/agent-mem.db --query "local memory system"
agent-mem export-sync --db ./.hindsight/agent-mem.db --out ./sync-bundle.jsonl
```

## Environment Variables

The CLI and library honor the `HINDSIGHT_DB` environment variable as a convenience for locating the SQLite file. Precedence for the database path is:

- CLI `--db` argument (highest priority)
- `HINDSIGHT_DB` environment variable
- Default: `agent-mem.db` (used when neither CLI argument nor env var is provided)

Examples:

- Use an environment variable so commands don't need `--db` every time:

```bash
export HINDSIGHT_DB=./.hindsight/agent-mem.db
agent-mem ingest --text "Note saved via env var"
```

- Override the environment with an explicit CLI argument:

```bash
export HINDSIGHT_DB=./.hindsight/agent-mem.db
agent-mem ingest --db ./other/agent-mem.db --text "This goes to other/agent-mem.db"
```

Notes:

- The `agent-mem init` / `agent-mem ingest` / `agent-mem search` and sync commands will resolve the DB path using the precedence above.
- Library classes such as `SQLiteMemoryStore` also fall back to `HINDSIGHT_DB` when a path is not supplied programmatically.

## Optional Integrations: sqlite-vec and FalkorDB

This project ships lightweight adapters for two optional integrations: `sqlite-vec` (local vector indexing) and FalkorDB (graph projection). They are optional extras and are not required for the core functionality.

Install the extras via pip:

```bash
pip install -e .[falkordb]
pip install -e .[sqlite-vec]
```

Notes:

- `sqlite-vec` is an SQLite extension that may require platform-specific build or a prebuilt binary. The code includes a fallback which stores embeddings as JSON in the database and performs a naive in-Python similarity search when the extension is not available.
- FalkorDB projection requires a running FalkorDB instance and the `falkordb` Python client; see the FalkorDB docs for startup instructions. The adapter will raise a helpful error if the client library is not installed.



## Directory Layout

```text
src/hindsight_local/
  ids.py                 deterministic content IDs
  models.py              dataclasses for memory objects
  cli.py                 command line interface
  storage/sqlite_store.py durable local store
  storage/vector_store.py vector abstraction and fallback
  graph/falkordb_projection.py optional graph projection
  sync/events.py         append-only sync event model
  sync/bundles.py        import/export bundles
  agent/memory_agent.py  reusable memory agent façade

agents/
  hindsight-memory-agent.md

skills/hindsight-memory/
  SKILL.md
```

## Design Notes

SQLite is the authoritative local store. FalkorDB Lite should be treated as a projection/index, not the only durable copy of the graph. Sync is event-sourced: field nodes export signed or hash-addressed memory events instead of trying to replicate graph databases directly.

## Next Steps

- Add real embedding provider adapters.
- Add sqlite-vec virtual table support once pinned to your target sqlite-vec version.
- Add FalkorDB Lite connection/runtime bootstrap.
- Add conflict adjudication policies and trust scoring.
- Add master ingest adapters for PostgreSQL/pgvector and Neo4j.
