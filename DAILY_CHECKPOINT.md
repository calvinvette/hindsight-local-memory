# Daily Checkpoint

Date: 2026-06-27
Branch: main

## Summary
This checkpoint captures the current local work in progress, including all unstaged files and the newly added architecture atlas.

## Modified files
- `Makefile`
- `README.md`
- `pyproject.toml`
- `src/hindsight_local/agent/memory_agent.py`
- `src/hindsight_local/cli.py`
- `src/hindsight_local/graph/falkordb_projection.py`
- `src/hindsight_local/storage/sqlite_store.py`
- `src/hindsight_local/storage/vector_store.py`
- `tests/test_store.py`

## New/untracked files
- `DAILY_CHECKPOINT.md`
- `docs/CODE_ATLAS.md`
- `scripts/graph_add_entry.py`
- `scripts/graph_regenerate.py`
- `scripts/vector_add_entry.py`
- `scripts/vector_regenerate.py`

## Notes
- The CLI app has been renamed to `agent-mem`.
- Default SQLite database basename now uses `agent-mem.db`.
- Optional integrations for `sqlite-vec` and FalkorDB Lite have been added.
- New management scripts were created for vector and graph operations.
- A new architecture atlas (`docs/CODE_ATLAS.md`) documents pure SQLite, sqlite-vec, and FalkorDB Lite flows.
- `pytest` was not installed in the current environment, so tests were not executed here.
