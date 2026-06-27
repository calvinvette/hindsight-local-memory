# Quickstart Developer Guide

## Local Development Setup

1. Clone the repository:

```bash
git clone https://github.com/calvinvette/hindsight-local-memory.git
cd hindsight-local-memory
```

2. Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install development dependencies:

```bash
pip install -e .[dev]
```

4. Initialize the local SQLite database:

```bash
python scripts/init_db.py --db ./.hindsight/agent-mem.db
```

## Optional Integration Paths

### SQLite only

This is the core local path. The SQLite store is the authoritative knowledge base.

```bash
export HINDSIGHT_DB=./.hindsight/agent-mem.db
agent-mem ingest --text "A local fact stored in SQLite"
agent-mem search --query "local fact"
```

### SQLite + sqlite-vec

Use `sqlite-vec` for local vector search when the extension is installed.

```bash
pip install -e .[sqlite-vec]
python -c "from hindsight_local.agent.memory_agent import HindsightMemoryAgent; agent=HindsightMemoryAgent('.hindsight/agent-mem.db', enable_vector=True); print(agent.remember('vector demo text'))"
```

If the extension is unavailable, the repository falls back to a JSON embedding table and a Python-based similarity search.

### SQLite + FalkorDB Lite

Use `FalkorDB Lite` for optional local graph projection.

```bash
pip install -e .[falkordb]
python -c "from hindsight_local.agent.memory_agent import HindsightMemoryAgent; agent=HindsightMemoryAgent('.hindsight/agent-mem.db', enable_falkordb=True); print('connected')"
```

This path preserves SQLite as the primary store and projects graph data into FalkorDB Lite.

### Combined SQLite + sqlite-vec + FalkorDB Lite

The full local developer path supports both optional indexes/projections.

```bash
pip install -e .[sqlite-vec,falkordb]
python -c "from hindsight_local.agent.memory_agent import HindsightMemoryAgent; agent=HindsightMemoryAgent('.hindsight/agent-mem.db', enable_vector=True, enable_falkordb=True); print(agent.remember('combined path demo'))"
```

## Developer Workflow

- Use `make lint` to run formatting and static checks.
- Use `make test` or `pytest -q` to run unit tests.
- Update `docs/CODE_ATLAS.md` and `docs/diagrams/` when adding new architecture flows.
