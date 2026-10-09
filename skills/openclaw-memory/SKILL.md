---
name: openclaw-memory
description: "Use Hindsight MCP from OpenClaw to retrieve project/global memory before substantial agent work and store concise, verified lessons afterward."
---

# OpenClaw Memory

Use the Hindsight MCP server as a first-class context source across OpenClaw sessions and agents. OpenClaw may also have built-in memory; use Hindsight for durable repository knowledge that should be accessible from other harnesses or explicitly scoped to a project/global database.

## Setup

OpenClaw discovers workspace skills in `<workspace>/skills/`; this repository's `skills/openclaw-memory/SKILL.md` is therefore directly discoverable when the repository is the configured workspace. Install it into the workspace `skills/` directory for another project or use `openclaw skills install` with a local skill source. Configure the MCP client under `mcp.servers` in `~/.openclaw/openclaw.json` as shown in [Hindsight Memory setup](../hindsight-memory/SKILL.md#openclaw).

Check server reachability with `openclaw mcp doctor hindsight-memory --probe`. The tools are made available subject to OpenClaw's tool profiles, policies, and per-agent MCP configuration. Use the Hindsight server's `memory_search` and `memory_remember` tools when they are exposed.

## Retrieve Before Work

Before substantial implementation, debugging, design, or research, search project memory with a task-specific query, `memory_scope: "project"`, and the absolute workspace `project_root`. Search global memory separately when cross-project guidance is relevant. Verify results against current code, docs, and tests; do not let stale memory override live evidence.

## Save Durable Lessons

After meaningful work, save a concise, verified lesson when it can help a later OpenClaw or other harness session: a confirmed root cause, repository convention, tested command, or design rationale. Use `memory_remember` with a short `text`, descriptive `title`, and `source_uri`. Set `memory_scope: "project"` and `project_root` for repository-specific notes; use `global` only for broadly reusable knowledge.

Never save secrets, personal/sensitive information, speculation, temporary task state, or a transcript. Confirm the tool result before stating a lesson was saved. If the server is unavailable or policy-filtered, continue with workspace evidence without claiming the memory workflow ran.
