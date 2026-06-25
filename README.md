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
python scripts/init_db.py --db ./.hindsight/hindsight.db
python examples/basic_ingest.py
```

The project works without `sqlite-vec` or FalkorDB installed. Those integrations are isolated behind adapters so you can add them later.

## CLI

```bash
hindsight init --db ./.hindsight/hindsight.db
hindsight ingest --db ./.hindsight/hindsight.db --text "Calvin is designing a local-first memory system."
hindsight search --db ./.hindsight/hindsight.db --query "local memory system"
hindsight export-sync --db ./.hindsight/hindsight.db --out ./sync-bundle.jsonl
```

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
