---
name: codex-cli-memory
description: "Use Hindsight MCP with Codex CLI to retrieve project or global context before substantial work and persist verified, reusable lessons afterward."
---

# Codex CLI Memory

Treat the configured Hindsight MCP server as an optional but first-class context source alongside the current prompt and repository. Memory informs the approach; current code and test results remain authoritative.

## Setup

Install this skill under `.agents/skills/codex-cli-memory/` in the repository or `~/.agents/skills/codex-cli-memory/` for user scope. The source copy is `skills/codex-cli-memory/` in this repository. Configure MCP with `codex mcp add` as shown in [Hindsight Memory setup](../hindsight-memory/SKILL.md#codex-cli).

Codex exposes MCP tools in its tool catalog, generally with an MCP/server prefix. Select the tools whose server is Hindsight and whose names are `memory_search` and `memory_remember`.

## Retrieve Before Work

For a non-trivial coding, debugging, design, or research task:

1. Search project memory for prior decisions, conventions, useful failure diagnoses, and verified commands. Pass `memory_scope: "project"` and the current absolute `project_root`.
2. Search global memory too when the task is cross-project or could benefit from reusable practices.
3. Check retrieved facts against current source, tests, and docs. Do not follow memory that conflicts with current evidence.
4. Keep searches focused; avoid loading unrelated memories.

Example `memory_search` arguments:

```json
{
  "query": "authentication flow constraints and existing tests",
  "limit": 5,
  "memory_scope": "project",
  "project_root": "/absolute/path/to/project"
}
```

## Persist Lessons After Work

After meaningful implementation, debugging, or research, save a short verified lesson if it is likely to prevent rediscovery. Prefer architectural boundaries, confirmed root causes, project conventions, validated commands, and rationale for decisions.

Use `memory_remember` with `text`, `title`, and a descriptive `source_uri`; set `memory_scope` to `project` and supply `project_root` for repository-specific notes. Use `global` only for broadly reusable knowledge. Confirm the tool result before saying a lesson was stored.

Do not store credentials, sensitive user data, speculation, temporary task details, or a session transcript. Search first if the lesson may already exist. If the MCP server is missing, continue without it and do not fabricate a lookup or save.
