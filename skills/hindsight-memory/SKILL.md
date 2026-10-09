---
name: hindsight-memory
description: "Install and configure Hindsight local memory and its MCP server for agent harnesses; use when integrating project/global SQLite memory into an agent workflow."
---

# Hindsight Memory Skill

Use this skill to add local-first memory to another project.

## When to Use

- The project needs durable local agent memory.
- The project must run offline or air-gapped.
- The project needs later synchronization with a central Hindsight memory system.
- The project benefits from graph and vector retrieval.

## Integration Steps

1. Add this repository as a dependency or copy `src/hindsight_local` into the project.
3. Initialize a local database:

```bash
agent-mem init --db ./.hindsight/agent-mem.db
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
agent-mem export-sync --db ./.hindsight/agent-mem.db --out ./sync-bundle.jsonl
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

## Install the MCP server

Install the Python package in a virtual environment or in a managed user environment that places `agent-mem-mcp` on `PATH`. For a local wheel:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install dist/hindsight_local_memory-0.1.0-py3-none-any.whl
```

Initialize a project or global database when setting up manually:

```bash
agent-mem init --db ./.hindsight/agent-mem.db
# or
agent-mem init --db ~/.hindsight/agent-mem.db
```

When calling MCP tools, pass `memory_scope` and (for project scope) `project_root`. Avoid setting `HINDSIGHT_DB` in the MCP server environment if agents need to choose project or global scope per call: an explicit `HINDSIGHT_DB` takes precedence over scope resolution. Use `HINDSIGHT_MEMORY_SCOPE` and `HINDSIGHT_PROJECT_ROOT` as defaults instead.

The server exposes `memory_search`, `memory_remember`, `memory_config`, and related init/relationship/sync tools over stdio. Harnesses may prefix MCP tool names; select the tools by their Hindsight server and base name.

## VS Code Integration

- Install the `agent-mem` CLI via pip:

```bash
pip install dist/hindsight_local_memory-0.1.0-py3-none-any.whl
```

- Initialize the local Hindsight/Agent-Mem database:

```bash
mkdir -p /tmp/hindsight
agent-mem init --db /tmp/hindsight/agent-mem.db
```

- Add the MCP server to the VS Code `mcp.json` configuration. For project memory, leave `HINDSIGHT_DB` unset so a tool call can explicitly select global scope when needed:

```json
{
  "mcpServers": {
    "hindsight-memory": {
      "type": "stdio",
      "command": "agent-mem-mcp",
      "env": {
        "HINDSIGHT_MEMORY_SCOPE": "project",
        "HINDSIGHT_PROJECT_ROOT": "${workspaceFolder}"
      }
    }
  }
}
```

For global-by-default memory, set `HINDSIGHT_MEMORY_SCOPE` to `global` and optionally set `HINDSIGHT_GLOBAL_HOME`. Tools can still select a different scope unless `HINDSIGHT_DB` is set.

## Claude Code

Install the skill in `.claude/skills/claude-code-memory/` for the project or `~/.claude/skills/claude-code-memory/` for the user. Add a project server in `.mcp.json`:

```json
{
  "mcpServers": {
    "hindsight-memory": {
      "type": "stdio",
      "command": "agent-mem-mcp",
      "env": {
        "HINDSIGHT_MEMORY_SCOPE": "project",
        "HINDSIGHT_PROJECT_ROOT": "${CLAUDE_PROJECT_DIR:-.}"
      }
    }
  }
}
```

Alternatively, register from the project root with `claude mcp add --transport stdio --scope project --env HINDSIGHT_MEMORY_SCOPE=project --env HINDSIGHT_PROJECT_ROOT="$PWD" hindsight-memory -- agent-mem-mcp`. Review and approve project-scoped servers when Claude Code prompts.

## Codex CLI

Install the skill under `.agents/skills/codex-cli-memory/` for the project or `~/.agents/skills/codex-cli-memory/` for the user. From the project root, run:

```bash
codex mcp add hindsight-memory \
  --env HINDSIGHT_MEMORY_SCOPE=project \
  --env HINDSIGHT_PROJECT_ROOT="$PWD" \
  -- agent-mem-mcp
codex mcp list
```

Codex stores MCP configuration in `~/.codex/config.toml` by default and supports trusted project configuration as well. Select the Hindsight `memory_search` and `memory_remember` MCP tools from the tool catalog.

## OpenCode

Install the skill in `.agents/skills/opencode-memory/` (or `.opencode/skills/opencode-memory/`) for project scope, or `~/.config/opencode/skills/opencode-memory/` for user scope. Add the local MCP server to project `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "hindsight-memory": {
      "type": "local",
      "command": ["agent-mem-mcp"],
      "environment": {
        "HINDSIGHT_MEMORY_SCOPE": "project",
        "HINDSIGHT_PROJECT_ROOT": "/absolute/path/to/project"
      },
      "enabled": true
    }
  }
}
```

Replace the project path with the absolute workspace path. OpenCode discovers `.agents/skills` and provides the MCP tools alongside its built-in tools.

## Pi Agent / OhMyPi

Pi supports project skills in `.pi/skills/` and `.agents/skills/`; user skills are under `~/.pi/agent/skills/` or `~/.agents/skills/`. Install `skills/pi-memory/` into one of those locations. For a Pi-compatible OhMyPi build, use its documented Pi skill/MCP paths and verify its CLI options because forks may change them.

From the project root, add a stdio server:

```bash
pi mcp add --local hindsight-memory \
  --env HINDSIGHT_MEMORY_SCOPE=project \
  --env HINDSIGHT_PROJECT_ROOT="$PWD" \
  -- agent-mem-mcp
pi mcp list
```

Pi writes project MCP configuration to `.pi/mcp.json`; the equivalent entry uses `command: "agent-mem-mcp"` and the two values in its `env` object. Use `/mcp` in a session to inspect the connection and tools.

## Hermes

Install the skill in `.agents/skills/hermes-memory/` or `.hermes/skills/hermes-memory/` for project use, or `~/.hermes/skills/hermes-memory/` for user scope. Hermes requires trusting the repository before loading its project skills: run `hermes skills trust` from that repository.

Add a stdio server to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  hindsight-memory:
    command: agent-mem-mcp
    env:
      HINDSIGHT_MEMORY_SCOPE: project
      HINDSIGHT_PROJECT_ROOT: "${workspaceFolder}"
```

After editing MCP configuration, start a new session or run `/reload-mcp`. Hermes has its own per-profile `memory` and `session_search`; use Hindsight when shared project/global memory across harnesses is needed rather than duplicating all profile memory.

## OpenClaw

OpenClaw discovers workspace skills directly from `<workspace>/skills/`, so `skills/openclaw-memory/` is directly available when this repository is the configured workspace. For another workspace, install the skill under that workspace's `skills/` directory or use `openclaw skills install` with a local skill source.

Add Hindsight to `~/.openclaw/openclaw.json`:

```json5
{
  mcp: {
    servers: {
      "hindsight-memory": {
        command: "agent-mem-mcp",
        transport: "stdio",
        enabled: true,
        env: {
          HINDSIGHT_MEMORY_SCOPE: "project",
          HINDSIGHT_PROJECT_ROOT: "/absolute/path/to/project",
        },
      },
    },
  },
}
```

Use an absolute project path, then validate the server with `openclaw mcp doctor hindsight-memory --probe`. OpenClaw's policies and per-agent settings still govern whether the tools are exposed.