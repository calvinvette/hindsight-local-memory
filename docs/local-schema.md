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
- `context_captures`

The current implementation uses SQLite FTS5 for text retrieval. `sqlite-vec` support belongs in `storage/vector_store.py` once the extension version and loading path are pinned for your runtime.

`context_captures` stores typed, local VS Code context records. The initial
capture types are:

- `editor`: language ID, document URI, workspace/session IDs, optional
  selection range, and optional selected text.
- `debugger`: debug type, lifecycle/stop state, reason, workspace/session IDs,
  and bounded stack-frame metadata. Variable values and debug-console contents
  are intentionally not part of this capture contract.

Selected editor text is also ingested as an HLM document/chunks so it can be
found through FTS; metadata-only captures remain typed capture records.
`capture_id` is the idempotency key: reusing it with identical data returns
the existing record, while conflicting data is rejected.
Each capture includes a `schema_version` (`hindsight.capture.v1`) so later
metadata migrations can be handled explicitly.

`SQLiteMemoryStore.query_graph(seed_id, relation, depth, limit)` provides
read-only traversal over `graph_edges` and hydrates known document, chunk,
entity, claim, and context-capture nodes. Depth is limited to 0–3 and edge
results to 1–100. Without a seed, it returns recent edges and recent capture
nodes. Unknown IDs remain visible as lightweight nodes. FalkorDB remains an
optional projection and is not required for local graph queries.
