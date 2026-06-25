# Local Schema

SQLite tables:

- `documents`
- `chunks`
- `chunks_fts`
- `entities`
- `claims`
- `graph_edges`
- `sync_events`
- `tombstones`

The current implementation uses SQLite FTS5 for text retrieval. `sqlite-vec` support belongs in `storage/vector_store.py` once the extension version and loading path are pinned for your runtime.
