---
name: pi-memory
description: "Use Hindsight MCP with Pi or a Pi-compatible OhMyPi agent to retrieve relevant project/global memory before work and save durable, verified lessons afterward."
compatibility: pi, ohmypi
---

# Pi / OhMyPi Memory

Use Hindsight MCP as an on-demand context source for non-trivial coding, debugging, design, or research. Search prior knowledge when useful, validate it against the current repository, and save only durable lessons learned.

## Setup

Pi supports project skills in `.pi/skills/` and the portable `.agents/skills/` location; user skills live under `~/.pi/agent/skills/` or `~/.agents/skills/`. Install this skill in one of those recognized locations. Its source copy is `skills/pi-memory/` in this repository. Configure MCP with `pi mcp add` or `.pi/mcp.json` as described in [Hindsight Memory setup](../hindsight-memory/SKILL.md#pi-agent-ohmypi).

In an interactive session, `/mcp` shows server and tool status. Pi usually names tools `mcp__<server>__<tool>`; select the configured Hindsight server's `memory_search` or `memory_remember` tool. For OhMyPi, use these instructions where the installed version supports Pi-compatible skills and MCP; check that fork's help/config docs for any changed command or path.

## Retrieve Before Work

For substantial work, call `memory_search` with a focused query and `memory_scope: "project"`, passing the active workspace's absolute `project_root`. Search `global` separately if broadly reusable knowledge could matter. Verify results against source and tests before relying on them; memory can be stale.

## Record Lessons Learned

After meaningful work, call `memory_remember` for confirmed lessons that will likely help future sessions: root causes, repository conventions, validated commands, or important design rationale. Provide a concise `text`, descriptive `title`, and a `source_uri`; use project scope plus `project_root` for repository-specific knowledge and global scope for cross-project guidance.

Do not store secrets, personal data, unverified theories, transient task state, or a chat transcript. Check the tool result for success before reporting that memory was saved. If Hindsight is unavailable, continue using the live repository and do not pretend the MCP call succeeded.
