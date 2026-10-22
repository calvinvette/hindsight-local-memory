# Local Sync and Agent Bricks Server Compatibility

## Direction

Hindsight remains a local-first memory node: SQLite is authoritative for local
writes and reads, and must continue to work when the network or Databricks is
unavailable. For connected deployments, the preferred server-side direction is
Databricks Agent Bricks' separation of managed **Agent Sessions** from
long-term **Agent Memory**, both backed by Lakebase, with Agent Bricks memory
pipelines responsible for distilling session history into durable memories.

The compatibility goal is to translate between these models without making
the local database depend on Agent Bricks' schema, availability, or search
implementation. This is a target architecture, not a claim that a Databricks
adapter or complete sync protocol exists today.

## Logical mapping

| Hindsight concept | Agent Bricks destination | Mapping guidance |
|---|---|---|
| Local actor / agent identity | `actor_id` | Maintain a stable, explicit mapping. Do not use a machine-specific unit ID as the actor identity unless each device is intentionally a separate person/agent. |
| Conversation/session event sequence | Agent Sessions session and session items | Preserve item order and source identity. Map a local conversation ID to a stable `session_id`; use `parent_session_id` only when the local conversation model represents a branch. |
| Hindsight event envelope | Integration/outbox metadata, plus a translated session or memory operation | Keep Hindsight event ID, schema version, source unit, timestamps, and provenance available for deduplication and audit. Do not assume a generic event is directly accepted by the managed session or memory API. |
| Curated fact, preference, or procedure | Agent Memory entry | Map the actor and any source session; translate the fact into entry content, a concise retrieval description, and a stable path/category. Preserve source event IDs or equivalent provenance in an integration-owned field/store where supported. |
| Hindsight document, chunk, claim, and graph projection | Local representation or explicitly mapped memory content | These richer structures do not have a one-to-one managed-memory equivalent. Retain them locally and translate only information with a defined server-side meaning. |
| Local FTS/vector/graph index | No required direct mapping | Treat search indexes as derived, backend-specific projections. Use the server's supported retrieval interface; do not assume managed Agent Memory uses a particular vector extension. |

Agent Sessions are the natural destination for conversation history; Agent
Memory is the destination for selected durable knowledge. They should not be
collapsed into a single table or blindly mirrored as equivalent Hindsight
documents.

## Local event and merge principles

- Keep the local SQLite database authoritative for local behavior. Remote
  outages must not prevent local capture or retrieval.
- Preserve accepted source events as an append-only history. Deduplicate
  delivery by stable event IDs and local objects by their stable domain IDs.
- Resolve concurrent knowledge changes at the claim/fact level rather than
  replacing an entire document or actor's memory.
- Represent corrections and retractions explicitly (for example, with
  `supersedes`, `retracts`, or `supports` relations) so translation does not
  erase the local audit trail.
- Treat embeddings as model-specific derived artifacts. Recompute them at the
  destination when the embedding model or dimensions do not match.

## Bundle format

The existing interchange format is JSON Lines: one local event per line.
Bundles remain useful for offline transfer even after a connected adapter is
added. The current code writes event dictionaries, for example:

```json
{"event_id":"evt_...","unit_id":"field-unit-7","actor_id":"agent-42","operation":"upsert_document","object_id":"doc_...","payload":{},"observed_at":"...","ingested_at":"...","schema_version":"hindsight.local.v1","parent_event_ids":[],"signature":null}
```

This is Hindsight's transport envelope, not an Agent Bricks API request.
Translation to session items or memory entries happens at the integration
boundary and must retain the envelope identity and provenance.

## Proposed data flow

```text
Local agent
  -> SQLite source of truth
     -> conversation/session records and local memory
     -> append-only sync outbox
          -> batch export / retrying connector
               -> translation and validation boundary
                    -> Agent Sessions (ordered session items)
                         -> Agent Bricks memory pipeline
                              -> Agent Memory (durable actor-scoped entries)

Agent Bricks retrieval
  -> managed memory/session API
  -> optional local cache or explicit translated projection
```

Local capture and local retrieval must not wait for any remote step. A
connected sync worker can upload batches and record acknowledgements. When the
worker is offline, the outbox remains available for a later retry or manual
bundle transfer. The remote integration should use Agent Bricks' supported
service interfaces; Lakebase being Postgres-backed does not imply that an
application should write directly to the managed tables or bypass the
Agent Bricks APIs and pipeline lifecycle.

## Ownership and loop prevention

Use an explicit owner for each kind of data:

- **Local source capture:** Hindsight owns local events and local SQLite
  materializations.
- **Remote raw conversation history:** Agent Sessions owns the accepted
  server-side session record after ingestion.
- **Server-side long-term memory:** Prefer the Agent Bricks memory pipeline as
  the owner of distillation and consolidation when that pipeline is enabled.
- **Hindsight local memory:** Hindsight retains its local representation and
  may optionally create a clearly marked projection of accepted remote facts.

Do not run independent Hindsight and Agent Bricks consolidation over the same
conversation stream and then continuously synchronize both results. That can
create duplicate, contradictory, or oscillating entries. If both systems
derive memory, define which system publishes canonical facts, how the other
consumes them, and how revisions/retractions are represented. Preserve
provenance so a server-generated memory can be traced to its source sessions
and the pipeline run that produced it.

Remote Agent Memory should not automatically overwrite local records. Any
down-sync or cache should be opt-in, identify server-derived entries, and
retain the remote entry identity and revision/provenance needed to refresh or
remove that projection safely.

## Event and delivery contract

The current JSONL `MemoryEvent` is a useful starting envelope, but reliable
translation requires a stronger contract:

- **Stable identity:** Generate an event ID once per logical operation and
  persist it. Re-exporting or retrying the same operation must not create a
  new ID.
- **Source and scope:** Include stable actor, source-unit, conversation/session,
  and object identifiers, with an explicit mapping to remote identifiers.
- **Ordering and provenance:** Preserve event time, sequence/order within a
  session, parent/correlation references, source schema version, and the
  original event ID when translating.
- **Versioned payloads:** Version the envelope and each translated payload;
  reject or quarantine unknown incompatible versions instead of silently
  dropping data.
- **Idempotent ingestion:** The receiver or adapter must detect previously
  accepted events and return the existing outcome for safe retries.
- **Acknowledgements and checkpoints:** Persist a per-destination cursor or
  acknowledged event set. Advance it only after confirmed remote acceptance;
  retain failed and unacknowledged events for retry.
- **Explicit mutations:** Define update, correction, retraction, and deletion
  semantics. Prefer append-only correction/retraction events in the local log
  even if the remote API represents the resulting current state as an update
  or delete.
- **Validation and observability:** Validate identity, payload shape, size,
  access scope, and destination mapping. Report per-event failures and counts;
  do not convert partial failures into success-shaped acknowledgements.

Local IDs should remain valid locally. An adapter-owned mapping table may
associate `(destination, local_id)` with a remote ID where the remote API
assigns identifiers. Keep this mapping separate from the domain identity so
retries and destination changes do not rewrite local event history.

## Lakebase's role

Lakebase is the managed Postgres foundation for the Agent Bricks stores, not a
substitute for the Agent Bricks session/memory contract. Use Agent Bricks
interfaces for session items, memory entries, and pipeline lifecycle unless
Databricks explicitly documents another supported integration point.

Lakebase capabilities may still be useful for a separate integration-owned
outbox, status/mapping tables, analytics, or search projection where the
deployment and product contracts permit it. Lakebase logical replication
replicates Postgres table changes; it does not translate SQLite entities or
resolve Hindsight-level conflicts. Do not equate database replication with
Agent Sessions ingestion or memory-pipeline execution.

Search is also an adapter concern. Hindsight currently provides SQLite FTS5;
the local vector adapter is not a production semantic-search implementation.
Agent Bricks' managed Agent Memory API documents its own retrieval behavior,
while Lakebase Search separately offers vector, BM25, and hybrid capabilities.
Use the supported managed-memory retrieval API for Agent Memory. Adopt
Lakebase Search only for an explicitly owned Lakebase projection, and treat
embeddings as model-specific derived data that may need recomputation.

## Current implementation and gaps

In the current checkout:

- SQLite is the local store and `sync_events` holds the event log.
- `export_sync_bundle` writes JSONL; `import_sync_bundle` inserts events into
  the log but does not replay them into documents, chunks, claims, or graph
  projections.
- There is no Agent Bricks client, Lakebase connector, remote authentication,
  push/pull worker, acknowledgement checkpoint, or remote-ID mapping.
- `export_events(since_event_id=...)` currently ignores its cursor and exports
  the complete log.
- Event IDs include generated timestamps in their hash input, so separate
  creations for the same logical operation are not reliable idempotency keys.
- Event signatures are modeled but are not populated by the current creation
  path.
- The model has no dedicated session-item abstraction corresponding to
  Agent Sessions, and no implemented session-to-memory pipeline.

Consequently, current bundle export/import is a basic interchange mechanism,
not durable synchronization or Agent Bricks integration.

## Implementation sequence

1. **Stabilize the local interchange contract.** Define session/conversation
   identity, event ordering, stable idempotency keys, schema versions, and
   correction/retraction operations. Fix delta export and ensure imported
   events can be safely replayed or explicitly documented as log-only.
2. **Separate session history from durable memory.** Represent ordered session
   items independently from extracted claims/facts while keeping both
   attributable to the same actor and source conversation. Do this
   incrementally so existing document/chunk storage remains usable.
3. **Specify and test translation.** Add pure mappings from local session
   items to Agent Sessions requests and from curated local facts to Agent
   Memory entries. Test ordering, identity stability, provenance, validation,
   and unsupported-field handling without requiring a live workspace.
4. **Add a remote delivery adapter.** Implement bounded batches, retries,
   per-destination checkpoints, partial-failure reporting, and a remote-ID
   mapping where needed. Remote unavailability must not block local
   operations.
5. **Integrate the server-side lifecycle.** Allow the deployment to send
   sessions to Agent Sessions and configure/trigger the Agent Bricks memory
   pipeline. Choose one canonical long-term-memory writer and define whether
   any pipeline outputs are projected back to Hindsight.
6. **Add optional down-sync and search projections only when required.**
   Define refresh, deletion, and conflict behavior for remote-derived local
   entries. Keep remote search backend details behind adapters.

Each stage should remain useful without Databricks credentials or network
access; live integration tests can be a separate opt-in tier.

## References

- [Agent Bricks stateful agents](https://docs.databricks.com/aws/en/agents/custom-agents/stateful-agents)
- [Managed Agent Sessions](https://docs.databricks.com/aws/en/agents/agent-memory/managed-sessions)
- [Managed Agent Memory](https://docs.databricks.com/aws/en/agents/agent-memory/managed-memory)
- [Memory pipelines](https://docs.databricks.com/aws/en/agents/agent-memory/memory-pipelines)
- [Lakebase overview](https://docs.databricks.com/aws/en/oltp/projects)
- [Lakebase logical replication](https://docs.databricks.com/aws/en/oltp/projects/logical-replication)
- [Lakebase Search](https://docs.databricks.com/aws/en/oltp/projects/lakebase-search)
