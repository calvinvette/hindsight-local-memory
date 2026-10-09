---
name: claude-code-memory
description: "Use Hindsight MCP from Claude Code to retrieve project or global memory before substantial work and save durable lessons after debugging, coding, or research."
---

# Claude Code Memory

Use the configured Hindsight MCP server as a first-class, on-demand source of context. Do not treat memory as a replacement for inspecting the current repository.

## Setup

Install this skill under `.claude/skills/claude-code-memory/` in the project or `~/.claude/skills/claude-code-memory/` for user scope. The source copy is `skills/claude-code-memory/` in this repository. Configure the stdio server as described in [Hindsight Memory setup](../hindsight-memory/SKILL.md#claude-code).

Claude Code prefixes MCP tools with the configured server name. Use the `memory_search` and `memory_remember` tools shown by `/mcp`; do not assume a fixed prefixed tool identifier.

## Retrieve Before Work

For non-trivial implementation, debugging, design, or research:

1. Search project memory for relevant decisions, conventions, previous diagnoses, and validated commands. Pass `memory_scope: "project"` and the current absolute `project_root`.
2. Search global memory as well when the task has cross-project relevance.
3. Verify important retrieved details against current files and tests. Current repository evidence takes precedence over stale memory.
4. Use focused queries and stop once relevant context is found.

Example `memory_search` arguments:

```json
{
  "query": "known SQLite lock behavior and tests for concurrent writes",
  "limit": 5,
  "memory_scope": "project",
  "project_root": "/absolute/path/to/project"
}
```

## Save Durable Lessons

After meaningful work, save a concise lesson when it captures verified knowledge likely to help future sessions: a root cause, non-obvious convention, reliable test command, or design decision. Use `memory_remember` with `text`, `title`, `source_uri`, and the appropriate `memory_scope`; include `project_root` for project memory.

```json
{
  "text": "Default-path tests must unset HINDSIGHT_DB and HINDSIGHT_MEMORY_SCOPE so developer environment settings do not mask the project default.",
  "title": "Isolate database path tests from environment settings",
  "source_uri": "project:example/testing",
  "memory_scope": "project",
  "project_root": "/absolute/path/to/project"
}
```

Save reusable guidance globally only when it applies across repositories. Do not save secrets, personal data, guesses, transient task state, or a transcript. Confirm the MCP result indicates the write succeeded; never claim a save based only on assistant text.

If Hindsight tools are unavailable, proceed with repository evidence and disclose the limitation only when it affects the result.
