# BEAM vs Hindsight Local Memory

## Scope

This document compares BEAM architecture principles with the current Hindsight Local Memory implementation and identifies concrete gaps.

Current Hindsight references used:

- docs/CODE_ATLAS.md
- README.md
- src/hindsight_local/storage/sqlite_store.py
- src/hindsight_local/agent/memory_agent.py
- src/hindsight_local/mcp_server.py

## Executive Summary

Hindsight currently has strong local durability and practical simplicity, but it is not BEAM-like in runtime behavior. It does not yet implement supervised worker topologies, process isolation by unit-of-work, mailbox-based flow control, or self-healing orchestration patterns.

This is not a flaw given project goals; it is a strategic design choice. If Hindsight needs to evolve toward large multi-agent concurrency, BEAM-inspired patterns can be introduced incrementally without replacing SQLite-first storage.

## High-Level Comparison

| Dimension | BEAM Principle | Hindsight Today | Gap Level |
|---|---|---|---|
| Concurrency unit | Lightweight isolated process per task/session | Python process with function-call style handlers and SQLite access | High |
| Communication model | Async message passing via mailboxes | Direct method calls and DB operations | High |
| Failure model | Let it crash + supervisor restart policy | Exceptions bubble; no supervisor hierarchy | High |
| Recovery semantics | Automatic restart strategies and isolation domains | Manual restart at process/container/tool level | High |
| Scheduling fairness | Runtime preemption by reductions | Python runtime and OS scheduling; no domain scheduler | Medium |
| State ownership | Process-local state, explicit ownership | Mostly persisted state in SQLite; minimal long-lived in-memory actors | Medium |
| Backpressure | Mailbox-aware flow control | SQLite busy_timeout + WAL; no queue-level policy | Medium |
| Distribution | Built-in node-to-node messaging and monitoring | No built-in distributed runtime | Medium |
| Zero-downtime evolution | Hot code upgrade model | Standard deploy/restart lifecycle | Medium |
| Observability model | Process tree introspection and links/monitors | Basic logs/events via sync/event tables and MCP responses | Medium |

## What Hindsight Already Does Well (BEAM-Adjacent)

1. Durable event trail:
- sync_events append-only log is aligned with event-oriented recovery practices.

2. Isolation via persistence boundary:
- SQLite as source of truth reduces in-memory inconsistency risk.

3. Explicit scope partitioning:
- Project/global memory scope resolution is a practical isolation boundary.

4. Resilience pragmatism:
- WAL + busy_timeout in SQLite improves contention behavior for concurrent writes.

These are good foundations for introducing BEAM-like coordination patterns.

## Gap Analysis by Capability

## 1. Supervision trees

Current state:
- No supervisor/worker hierarchy for memory jobs, ingestion tasks, or MCP tool execution.

Impact:
- A failed operation is isolated only by request boundary, not by formal restart policy.
- Multi-step tasks (ingest -> embed -> project -> sync) have limited automatic recovery semantics.

Gap:
- High

Recommended direction:
- Introduce a local supervisor abstraction in Python:
  - Supervisor manages named workers (ingest_worker, embed_worker, sync_worker).
  - Per-worker restart policy (always, transient, never).
  - Failure counters and exponential backoff.

## 2. Message-passing workflow execution

Current state:
- Direct call-chain execution from CLI/MCP into agent/store.

Impact:
- Coupled control flow; difficult to apply backpressure, deferred retries, or priority scheduling.

Gap:
- High

Recommended direction:
- Add an internal command queue (SQLite-backed or in-memory + durable checkpointing):
  - Tool calls enqueue commands.
  - Workers consume commands asynchronously.
  - Command status table supports queued/running/failed/retried/completed.

## 3. Failure containment and restart semantics

Current state:
- Failures surface as exceptions/result errors; no restart domains.

Impact:
- Partial pipeline failures require caller retries.
- Repeated failures can produce brittle operational behavior under load.

Gap:
- High

Recommended direction:
- Add restart domains:
  - Per pipeline stage retries.
  - Dead-letter queue for permanent failures.
  - Idempotency keys on commands/events.

## 4. Backpressure and mailbox control

Current state:
- No mailbox metrics/limits.
- SQLite lock management is present, but queue pressure is not modeled.

Impact:
- Request bursts can overwhelm downstream operations.

Gap:
- Medium

Recommended direction:
- Add queue-level controls:
  - Max in-flight by worker type.
  - Admission control at MCP boundary.
  - Priority lanes for small read requests vs heavy write pipelines.

## 5. Long-lived actor state vs persistent state

Current state:
- State is mostly persisted; minimal long-lived runtime state.

Impact:
- Simpler correctness model, but misses fast in-memory coordination patterns.

Gap:
- Medium

Recommended direction:
- Keep SQLite-authoritative model.
- Add minimal coordinator actors with ephemeral state and deterministic recovery from sync_events.

## 6. Multi-node/distributed orchestration

Current state:
- Sync bundle model exists for offline reconciliation.
- No process-level distributed runtime or cluster topology.

Impact:
- Great for disconnected operation, less ideal for real-time cross-node orchestration.

Gap:
- Medium

Recommended direction:
- Preserve bundle model as primary.
- Optionally add a peer relay process with explicit replication channels (still event-first).

## 7. Runtime introspection

Current state:
- Limited process-lifecycle introspection beyond logs and DB inspection.

Impact:
- Harder to reason about live system pressure and failure hotspots.

Gap:
- Medium

Recommended direction:
- Add lightweight runtime stats endpoint/command:
  - Worker health
  - Queue depth
  - Retry counts
  - Event lag

## Prioritized Roadmap (BEAM-Inspired, SQLite-Preserving)

### Phase 1: Supervisor and queue foundations

- Add internal command queue and worker loop.
- Introduce supervisor abstraction with restart policies.
- Add command status persistence and idempotency tokens.

Expected outcome:
- Controlled retries and crash recovery without redesigning storage.

### Phase 2: Backpressure and observability

- Add queue limits and per-tool admission control.
- Add runtime diagnostics command and MCP status tool.
- Track worker lifecycle metrics and failure reasons.

Expected outcome:
- Improved operational predictability under concurrent load.

### Phase 3: Distributed and advanced orchestration options

- Add optional peer relay for near-real-time event forwarding.
- Add conflict adjudication hooks for concurrent updates.
- Add explicit pipeline orchestration metadata in sync_events.

Expected outcome:
- Stronger multi-agent/multi-node coordination while retaining offline-first semantics.

## Decision Guidance

When to adopt more BEAM-like patterns:

- You expect sustained concurrent write-heavy agent workloads.
- You need automatic recovery with bounded operator intervention.
- You need predictable behavior during bursty multi-agent runs.

When current architecture is sufficient:

- Single-node or small-team usage.
- Moderate concurrency with occasional write contention.
- Priority is minimal footprint and straightforward operations.

## Bottom Line

Hindsight and BEAM solve different primary problems:

- BEAM is a runtime architecture for resilient concurrent processes.
- Hindsight is a local-first memory substrate with durable event sync.

The strongest strategy is not to re-platform Hindsight onto BEAM, but to adopt BEAM principles incrementally where they improve concurrency safety and self-healing behavior, while keeping SQLite as the authoritative core.
