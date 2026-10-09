---
name: copilot-memory
description: "Use the Hindsight MCP memory server from VS Code to retrieve relevant project or global context before work, and to persist durable lessons learned after debugging, implementation, or research."
user-invocable: true
---

# Copilot Memory

Use the Hindsight MCP server as an opt-in, first-class source of context while working in VS Code. Retrieve relevant memories before substantial work, and save concise, reusable lessons when a task produces durable knowledge.

## Availability

The workspace should configure the Hindsight server in `.vscode/mcp.json` or the user's MCP configuration. The server command is `agent-mem-mcp`; see [the Hindsight Memory skill's VS Code integration](../hindsight-memory/SKILL.md#5-vs-code-integration) for installation and configuration.

The MCP server exposes these relevant tools:

- `memory_search` to retrieve memories.
- `memory_remember` to save a memory.
- `memory_config` to inspect the active memory scope and database path.

If the server or tools are unavailable, continue normally using repository files and the current conversation. Do not claim to have searched or stored memories when the calls did not succeed.

## Before Work: Retrieve Context

For a non-trivial coding, debugging, design, or research task:

1. Identify the current project root and the task's key concepts, symbols, errors, or constraints.
2. Search project memory for relevant prior decisions, conventions, known failures, and validated commands. Use the `memory_search` MCP tool with a focused natural-language query, `memory_scope: "project"`, and `project_root` set to the current workspace root.
3. When the task has cross-project relevance, also search global memory using `memory_scope: "global"`.
4. Apply retrieved memories as context, not as unquestionable truth. Verify important claims against current code, tests, and documentation; newer repository evidence takes precedence over stale memory.
5. Keep only relevant findings in working context. Do not repeat broad searches when the initial results answer the question.

Example tool arguments for project context:

```json
{
  "query": "SQLite concurrency, database path conventions, and tests related to the current task",
  "limit": 5,
  "memory_scope": "project",
  "project_root": "/absolute/path/to/workspace"
}
```

Example tool arguments for reusable context:

```json
{
  "query": "reusable Python packaging or MCP integration lessons relevant to this task",
  "limit": 5,
  "memory_scope": "global"
}
```

## After Work: Save Lessons

After completing meaningful debugging, implementation, or research, consider whether the work produced a durable lesson that would save effort in a future session. Store only useful knowledge, such as:

- A verified repository convention or important architectural boundary.
- A root cause, non-obvious failure mode, or debugging technique that was confirmed.
- A test, build, or setup command that works, including relevant prerequisites.
- A design decision and its rationale that future changes should preserve.
- A user preference that is explicit and likely to recur.

Use `memory_remember` with a short, factual note. Put repository-specific lessons in project memory using the workspace root; put broadly reusable lessons in global memory. Include a descriptive title and a source URI that identifies the project or lesson type.

Example project lesson:

```json
{
  "text": "Default-path tests must clear HINDSIGHT_DB and HINDSIGHT_MEMORY_SCOPE; the developer environment may define them and otherwise masks the project default.",
  "title": "Isolate database path tests from environment settings",
  "source_uri": "project:hindsight-local-memory/testing"
}
```

Example tool scope arguments for storing a project lesson:

```json
{
  "memory_scope": "project",
  "project_root": "/absolute/path/to/workspace"
}
```

When calling the tool, combine these scope arguments with the lesson fields. Check the result for success and retain its returned identifier only when useful for later follow-up.

## Memory Quality and Safety

- Save lessons, not a transcript of the task. Prefer one compact, standalone fact over a chronology.
- Do not store secrets, credentials, private user data, or sensitive environment/configuration values.
- Avoid storing guesses, unverified diagnoses, temporary task state, or information already documented clearly in the repository.
- Search before saving when duplication is likely; update your understanding if an existing memory already covers the lesson.
- Use the narrowest suitable scope: project for repository-specific facts, global for reusable cross-project guidance.
- Do not let memory replace inspecting the current repository, running relevant checks, or asking the user when requirements are ambiguous.

## Interaction Pattern

Treat memory as a normal context source, alongside the current request and repository evidence:

- At task start, search for context that could change the approach.
- During work, follow verified memories where they still match current evidence.
- At task completion, save a durable lesson when one was learned.
- In the response, mention memory context only when it materially affected the result or when memory retrieval/storage failed and that limitation matters.
