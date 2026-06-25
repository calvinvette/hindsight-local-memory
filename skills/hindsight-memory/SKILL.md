# Hindsight Memory Skill

Use this skill to add local-first memory to another project.

## When to Use

- The project needs durable local agent memory.
- The project must run offline or air-gapped.
- The project needs later synchronization with a central Hindsight memory system.
- The project benefits from graph and vector retrieval.

## Integration Steps

1. Add this repository as a dependency or copy `src/hindsight_local` into the project.
2. Initialize a local database:

```bash
hindsight init --db ./.hindsight/hindsight.db
```

3. Use the agent façade:

```python
from hindsight_local.agent.memory_agent import HindsightMemoryAgent

memory = HindsightMemoryAgent(".hindsight/hindsight.db")
memory.remember("A fact or observation", source_uri="project:note")
hits = memory.recall("fact observation")
```

4. Export sync bundles when reconnecting to the master system:

```bash
hindsight export-sync --db ./.hindsight/hindsight.db --out ./sync-bundle.jsonl
```

## Design Constraints

- SQLite is the local source of truth.
- sqlite-vec, FTS5, and FalkorDB Lite are indexes/projections.
- Sync via append-only events, not raw DB replication.
- Every claim should include provenance and confidence.
- Every embedding should include an embedding model ID.

## Extension Points

- Replace `HashingEmbedder` with a local embedding model.
- Implement sqlite-vec DDL and KNN search in `SQLiteVecAdapter`.
- Implement richer entity and claim extraction.
- Add FalkorDB Lite bootstrap and projection replay.
- Add master importers for PostgreSQL/pgvector and Neo4j.
