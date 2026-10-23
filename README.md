# Hindsight Local Memory

A local-first, air-gap-friendly memory node for agentic systems. The project is designed to run locally with SQLite as the durable source of truth, optional `sqlite-vec` for vector search, and optional FalkorDB Lite as a graph query projection. For connected deployments, the intended server-side direction is compatible with Databricks Agent Bricks: translate local conversation history to Agent Sessions and let the managed memory pipeline produce Agent Memory, while retaining SQLite as the local authority.

## Goals

- Local memory for field units, laptops, labs, edge boxes, and disconnected environments.
- Durable append-only sync log for later translation and delivery to a server-side memory system.
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

## Connected deployment direction

The local node remains independently usable and authoritative when offline.
When connected, a future adapter should translate ordered local conversation
items to Agent Bricks Agent Sessions and use the Agent Bricks memory pipeline
to derive server-side Agent Memory. Do not treat Hindsight documents or raw
events as direct equivalents of managed memory entries, or write directly to
Lakebase tables in place of the supported Agent Bricks interfaces. Keep
delivery retryable and idempotent, and define a single owner for long-term
memory consolidation to avoid duplicate or conflicting memories.

This integration is a design direction, not a feature currently implemented.
See the [sync and Agent Bricks compatibility design](./docs/sync-design.md) and
the [Agent Bricks comparison](./docs/AGENTBRICKS_COMPARISON.md) for the data
mapping, delivery requirements, and implementation gaps.

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

## Install From GitHub

Use the installer directly from raw GitHub content:

```bash
curl -fsSL https://raw.githubusercontent.com/calvinvette/hindsight-local-memory/main/scripts/install-hindsight.sh | bash
```

```bash
wget -qO- https://raw.githubusercontent.com/calvinvette/hindsight-local-memory/main/scripts/install-hindsight.sh | bash
```

The installer prompts for:

- Install variant: `node` or `python`.
- Install target: project-local (`npm install`), local virtualenv (`python -m venv` + `pip install`), or global (`npm -g` / system `pip`).
- Memory mode: `project` or `global`.

You can run non-interactively with environment variables:

```bash
HINDSIGHT_INSTALL_VARIANT=python \
HINDSIGHT_INSTALL_TARGET=venv \
HINDSIGHT_MEMORY_MODE=project \
curl -fsSL https://raw.githubusercontent.com/calvinvette/hindsight-local-memory/main/scripts/install-hindsight.sh | bash
```

```bash
HINDSIGHT_INSTALL_VARIANT=node \
HINDSIGHT_INSTALL_TARGET=global \
HINDSIGHT_MEMORY_MODE=global \
wget -qO- https://raw.githubusercontent.com/calvinvette/hindsight-local-memory/main/scripts/install-hindsight.sh | bash
```

Variant command lines:

- Node (project): `npm install --save hindsight-local-memory`
- Node (global): `npm install -g hindsight-local-memory`
- Python wheel (local venv): `python3 -m venv .venv && . .venv/bin/activate && python -m pip install "https://github.com/calvinvette/hindsight-local-memory/releases/download/v0.1.0/hindsight_local_memory-0.1.0-py3-none-any.whl"`
- Python wheel (global): `python3 -m pip install "https://github.com/calvinvette/hindsight-local-memory/releases/download/v0.1.0/hindsight_local_memory-0.1.0-py3-none-any.whl"`

If your wheel URL differs, set `HINDSIGHT_PYTHON_WHL_URL` before running the installer.

## CLI

```bash
agent-mem init --db ./.hindsight/agent-mem.db
agent-mem ingest --db ./.hindsight/agent-mem.db --text "Calvin is designing a local-first memory system."
agent-mem search --db ./.hindsight/agent-mem.db --query "local memory system"
agent-mem export-sync --db ./.hindsight/agent-mem.db --out ./sync-bundle.jsonl
```

## MCP Interface

The package now includes an MCP stdio server binary:

```bash
agent-mem-mcp
```

This server supports the stateless MCP protocol release `2026-07-28`.

- No session handshake is required.
- Clients can optionally call `server/discover` to fetch capabilities and supported protocol versions.
- `tools/list` includes cache hints (`ttlMs` and `cacheScope`).
- Legacy `initialize` is still accepted for backward compatibility.

The MCP tools include:

- `memory_config`
- `memory_init`
- `memory_remember`
- `memory_search`
- `memory_graph_query`
- `memory_capture_editor_state`
- `memory_capture_debugger_state`
- `memory_relate`
- `memory_export_sync`
- `memory_import_sync`

Each tool accepts optional `memory_scope` (`project` or `global`), `project_root`, and `db_path` to support multi-agent setups sharing either one global DB or one DB per project.

Editor captures store typed editor/workspace/session metadata and optional
user-selected text. Debugger captures store typed session state and bounded
stack-frame metadata; variable values and debug-console contents are not
accepted. Capture records are local and can be searched when selected text is
included. Graph queries are read-only and bound traversal depth and result
count.

## Local JSON Bridge

For integrations where MCP is unavailable or disabled by policy, the CLI
provides a separate line-delimited JSON interface over the same HLM library
and SQLite store:

```bash
agent-mem bridge
```

Send one JSON request per line. Each response contains the matching `id`, the
bridge version (`hindsight.json-bridge.v1`), and either `result` or `error`.
Requests may include the same version to fail fast on incompatible versions.
Call `memory.capabilities` first: it returns the bridge and package versions,
the supported method list, and the size limits, so a client can adapt to older
or newer HLM installs. Request lines larger than 2 MiB are rejected without
being buffered.

The supported methods are `memory.capabilities`, `memory.config`,
`memory.search`, `memory.remember`, `memory.relate`, `memory.graph_query`,
`memory.capture_editor_state`, `memory.capture_debugger_state`,
`memory.list_captures`, `memory.get_capture`, `memory.delete_capture`, and
`memory.delete_document`. Search, list, and get results are truncated per item
(2000 characters by default, adjustable with `max_chars`) and flag
`text_truncated` or `content_truncated`. Deleting a capture or document removes
its chunks, search-index rows, embeddings, graph edges, and the content copies
in the local sync log, and leaves a content-free tombstone and `forget` event so
a later sync can propagate the deletion. Delete and list operations are
intentionally not exposed as MCP tools. For example:

```json
{"id":1,"method":"memory.graph_query","params":{"seed_id":"entity_123","depth":2,"limit":25}}
```

The bridge is a non-MCP local process interface, not a policy bypass. It still
requires authorization to launch the HLM executable and access its configured
local database. Follow the environment's approved extension/process and data
handling policies.

## Environment Variables

The CLI and library honor the `HINDSIGHT_DB` environment variable as a convenience for locating the SQLite file. Precedence for the database path is:

- CLI `--db` argument (highest priority)
- `HINDSIGHT_DB` environment variable
- Scope-aware default from `HINDSIGHT_MEMORY_SCOPE`:
  - `project` (default): `./.hindsight/agent-mem.db` under the active project root
  - `global`: `~/.hindsight/agent-mem.db`

Optional scope controls:

- `HINDSIGHT_MEMORY_SCOPE`: `project` or `global`
- `HINDSIGHT_PROJECT_ROOT`: explicit root used when scope is `project`
- `HINDSIGHT_GLOBAL_HOME`: explicit directory used when scope is `global`

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
