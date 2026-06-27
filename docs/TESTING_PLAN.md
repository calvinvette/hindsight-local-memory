# Testing Plan

## Goals

- Verify core SQLite storage and FTS search.
- Validate optional sqlite-vec adapter behavior and fallback path.
- Validate optional FalkorDB Lite projection wiring.
- Confirm CLI commands honor `HINDSIGHT_DB` and `--db` precedence.

## Recommended tests

### Unit tests

- `tests/test_store.py`
  - ingest text
  - search via FTS
  - default SQLite database basename

- Add tests for `SQLiteVecAdapter`
  - `available()` fallback behavior
  - `ensure_vector_table()` creates fallback tables when necessary
  - `knn_search_fallback()` returns ranked candidates

- Add tests for `FalkorDBProjection`
  - import failure with missing `falkordb` dependency
  - projection methods exercise query generation when the client is available

### Integration tests

- `agent-mem` CLI end-to-end:
  - init database
  - ingest sample text
  - search sample text
  - export sync bundle

- Optional `sqlite-vec` path:
  - enable vector mode and confirm the adapter can upsert embeddings
  - verify fallback table exists if the extension is unavailable

- Optional FalkorDB Lite path:
  - enable graph projection and verify connect() can initialize a local graph object
  - simulate project_document/project_edge/project_claim calls

## Manual validation

- Review `docs/CODE_ATLAS.md` diagram images render correctly in markdown viewers.
- Confirm `docs/diagrams/*.mmd` match the generated PNG files.
- Check that `README.md` and `docs/QUICKSTART-DEVELOPER.md` include the combined optional path.
