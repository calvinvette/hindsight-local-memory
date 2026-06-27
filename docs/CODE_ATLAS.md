# Code Atlas

## Overview

This repository is a local-first memory node. The authoritative storage is SQLite, and the project supports two optional local indexes/projections:

- `sqlite-vec` for local vector search.
- FalkorDB Lite for local graph projection and knowledge-base queries.

The architecture is intentionally lightweight and designed for offline or air-gapped environments.

## Pure SQLite Flow

![Pure SQLite flow](docs/diagrams/sqlite-flow.png)

### Key points

- SQLite is the source of truth.
- Document ingest writes durable records and append-only sync events.
- Retrieval uses SQLite FTS5 for text search.

## Optional sqlite-vec Flow

![Optional sqlite-vec flow](docs/diagrams/sqlite-vec-flow.png)

### Vector flow details

- `HindsightMemoryAgent(enable_vector=True)` initializes `SQLiteVecAdapter`.
- `SQLiteVecAdapter.ensure_vector_table()` creates a vector table using `sqlite-vec` if available.
- If the extension is unavailable, the adapter falls back to a JSON blob table and performs in-Python similarity search.
- Embedding support is optional and isolated from the core SQLite storage.

## Optional FalkorDB Lite Flow

![Optional FalkorDB Lite flow](docs/diagrams/falkordb-lite-flow.png)

### FalkorDB Lite notes

- FalkorDB Lite is treated as an optional projection, not as the authoritative store.
- The local SQLite DB remains the primary knowledge base.
- The adapter supports a local FalkorDB Lite instance via the same lightweight `falkordb` client.
- This repository targets local KB semantics rather than full enterprise graph replication.

## Combined sqlite-vec + FalkorDB Lite Flow

![Combined sqlite-vec + FalkorDB Lite flow](docs/diagrams/sqlite-vec-falkordb-flow.png)

### Combined optional flow notes

- Both vector search and graph projection are optional extensions on top of SQLite.
- The SQLite store remains authoritative while `sqlite-vec` indexes embeddings and FalkorDB Lite projects graph semantics.
- This path supports local KB use cases with both semantic retrieval and graph exploration.

## Component map

- `src/hindsight_local/storage/sqlite_store.py`
  - durable SQLite document store
  - FTS5 search
  - append-only sync event export/import
- `src/hindsight_local/storage/vector_store.py`
  - optional `sqlite-vec` adapter
  - JSON fallback for local embeddings
- `src/hindsight_local/graph/falkordb_projection.py`
  - optional FalkorDB Lite graph projection
- `src/hindsight_local/agent/memory_agent.py`
  - façade that wires SQLite, vector indexing, and graph projection
- `scripts/` 
  - operational helpers for managing the SQLite store, vector table, and graph projection
