# Deployment

## Deployment Context

This repository is designed for local-first deployment scenarios, including:

- developer laptops
- air-gapped edge nodes
- local memory appliances

The primary runtime is a local SQLite file. Optional indexes and projections are supported with `sqlite-vec` and FalkorDB Lite.

## Installation

Install the package in editable mode for local development:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For optional vector search and graph projection:

```bash
pip install -e .[sqlite-vec,falkordb]
```

## Configuration

The runtime looks for the SQLite database path in the following order:

1. CLI `--db` argument
2. `HINDSIGHT_DB` environment variable
3. default fallback: `agent-mem.db`

Use a local hidden directory for clean deployments:

```bash
mkdir -p .hindsight
export HINDSIGHT_DB=./.hindsight/agent-mem.db
```

## Running the service

There is no daemon process by default. Use the CLI and local scripts for operations:

```bash
agent-mem init --db ./.hindsight/agent-mem.db
agent-mem ingest --db ./.hindsight/agent-mem.db --text "Deployable local memory"
agent-mem search --db ./.hindsight/agent-mem.db --query "Deployable"
```

## Optional deployment notes

- `sqlite-vec` may require a platform-specific SQLite extension.
- FalkorDB Lite requires the `falkordb` client and a local FalkorDB Lite instance.
- The SQLite database remains the authoritative source of truth even with optional projections enabled.

## Artifacts

- `agent-mem.db` (default SQLite database file)
- `.hindsight/agent-mem.db` (recommended deployment location)
- `docs/diagrams/*.png` (architecture visuals)
- `docs/diagrams/*.mmd` (source diagrams)
