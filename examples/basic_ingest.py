from hindsight_local.agent.memory_agent import HindsightMemoryAgent

agent = HindsightMemoryAgent(".hindsight/hindsight.db")
agent.remember(
    "SQLite is the durable local source of truth. FalkorDB Lite is a graph projection. Sync uses append-only memory events.",
    source_uri="example:architecture",
    title="Local Hindsight architecture",
)
for hit in agent.recall("graph projection sync events"):
    print(hit["chunk_id"], hit["text"][:120])
