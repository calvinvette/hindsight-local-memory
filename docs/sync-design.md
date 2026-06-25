# Sync Design

The local node should not try to replicate SQLite to PostgreSQL or FalkorDB to Neo4j directly. Instead, it exports append-only `MemoryEvent` records.

## Merge Policy

- Preserve all events.
- Deduplicate by deterministic object IDs and event IDs.
- Prefer claim-level conflict handling over document-level replacement.
- Use `supersedes`, `retracts`, and `supports` relations instead of destructive updates.
- Treat embeddings as model-specific artifacts. Recompute centrally when model parity is not guaranteed.

## Bundle Format

JSON Lines, one event per line.

```json
{"event_id":"evt_...","operation":"upsert_document","object_id":"doc_...","payload":{}}
```

## Master Import Target

- PostgreSQL tables mirror SQLite tables.
- pgvector indexes central embeddings.
- Neo4j receives graph projections from accepted events.
