---
name: opencode-memory
description: "Use Hindsight MCP with OpenCode to retrieve relevant project/global memory before substantial work and store verified lessons learned after a task."
compatibility: opencode
---

# OpenCode Memory

Use Hindsight MCP as a first-class source of prior context when it can improve a coding, debugging, design, or research task. Treat its contents as leads to verify, not as a substitute for current repository evidence.

## Setup

OpenCode discovers skills in `.opencode/skills/`, `.agents/skills/`, and `~/.config/opencode/skills/`. Install this skill under `.agents/skills/opencode-memory/` for project scope or the user skills directory for global scope. The source copy is `skills/opencode-memory/` in this repository. Configure the local MCP server using [Hindsight Memory setup](../hindsight-memory/SKILL.md#opencode).

Use the Hindsight MCP `memory_search` and `memory_remember` tools from the available tool list. OpenCode may prefix their names with the MCP server identifier.

## Retrieve Relevant Context

Before substantial work, search project memory using the task's specific terms and pass `memory_scope: "project"` plus the current absolute `project_root`. Search global memory separately for cross-project practices. Verify relevant decisions, diagnoses, or commands against the repository; current evidence wins when it conflicts. Keep the retrieval narrow and stop when the results are sufficient.

## Save Verified Lessons

After completing meaningful work, use `memory_remember` to save a concise, standalone lesson only when it is durable and useful later. Include a descriptive `title`, a `source_uri` such as `project:repo/testing`, and `memory_scope: "project"` with the absolute `project_root`. Use global scope only for advice that generalizes across repositories.

Save confirmed conventions, root causes, reliable commands, or design rationale. Do not save secrets, private information, guesses, one-off task state, or a chronological transcript. Confirm the tool result indicates success. If the MCP server is unavailable, proceed normally and do not claim memory was consulted or updated.
