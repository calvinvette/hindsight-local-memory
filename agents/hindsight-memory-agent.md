# Hindsight Memory Agent

## Purpose

Use this agent when a project needs durable local memory, local retrieval, or field-unit synchronization with a larger Hindsight memory system.

## Responsibilities

1. Ingest text, documents, observations, and extracted facts.
2. Create deterministic IDs for documents, chunks, entities, claims, and edges.
3. Store authoritative local state in SQLite.
4. Use vector and graph indexes as projections.
5. Export append-only sync bundles for master reconciliation.
6. Import remote bundles without overwriting local knowledge destructively.

## Operating Rules

- Never treat graph projection state as the only durable source of truth.
- Preserve provenance and confidence for every claim.
- Prefer adding superseding/retracting events over deleting facts.
- Keep embedding model IDs attached to every vector.
- Preserve air-gap compatibility: all sync should work through files.

## Example Usage

```python
from hindsight_local.agent.memory_agent import HindsightMemoryAgent

memory = HindsightMemoryAgent(".hindsight/hindsight.db")
memory.remember("Important observation", source_uri="field:note:001")
print(memory.recall("important"))
memory.export_sync("sync-bundle.jsonl")
```
