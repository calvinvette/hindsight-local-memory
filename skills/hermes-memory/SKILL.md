---
name: hermes-memory
description: "Use the Hindsight MCP tools from Hermes Agent to retrieve cross-session project/global knowledge before work and persist verified lessons learned."
version: 1.0.0
platforms: [macos, linux, windows]
---

# Hermes Memory

Hermes has built-in profile memory and session search. Use Hindsight as a complementary, SQLite-backed memory that can be shared across agent harnesses and scoped per project or globally; avoid duplicating every built-in profile fact into Hindsight.

## Setup

Hermes reads skills from `~/.hermes/skills/` and supports trusted project skills at `.hermes/skills/` and `.agents/skills/`. For this project, make `skills/hermes-memory/` available under a recognized location. Project skills must be trusted once with `hermes skills trust` from the repository. Configure Hindsight as an stdio MCP server in `~/.hermes/config.yaml` using the instructions in [Hindsight Memory setup](../hindsight-memory/SKILL.md#hermes).

MCP tools are registered with a server prefix. Find the Hindsight server's `memory_search` and `memory_remember` tools in the available tool catalog; after changing MCP config, use `/reload-mcp` or start a new session.

## Retrieve Before Work

For non-trivial coding, debugging, design, or research, search Hindsight project memory with a focused query and `memory_scope: "project"`, passing the current absolute `project_root`. Search global scope too for cross-project lessons. Use Hermes' built-in memory and session search for personal/profile facts or past conversation details; use Hindsight for repository knowledge shared across harnesses. Verify retrieved facts against the current workspace.

## Save Lessons After Work

Save a concise Hindsight memory only when the task produced verified, durable knowledge that will help a later session: a root cause, repository convention, working command, or design decision. Use `memory_remember` with `text`, `title`, `source_uri`, and project scope plus `project_root` for repository-specific facts. Use global scope for reusable guidance across projects.

Do not store credentials, private data, guesses, transient state, or a task transcript. Do not claim a save unless the tool result confirms it. If Hindsight MCP is unavailable, continue with Hermes' own memory and current repository evidence.
