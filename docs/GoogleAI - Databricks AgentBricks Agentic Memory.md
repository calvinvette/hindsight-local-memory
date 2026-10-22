# Google AI Export

*Exported: 10/20/2026, 1:28:51 PM*

---

## Turn 1

### Question

🧠 Core Architecture: Sessions vs. Memory

### Answer

In Databricks Agent Bricks, agent state management is separated into two primary mechanisms: Agent Sessions (short-term episodic memory) and Agent Memory (long-term derived memory). These managed stores are backed by Lakebase to maintain continuity across various frameworks.

---

Databricks handles an agent's state by completely separating immediate chat context from long-term factual learning. ComponentFocus & TypeBehavior & LifecycleStorage TechAgent SessionsShort-term / EpisodicStores the single-interaction working state (messages, tool calls, and reasoning traces). Read/appended per turn; independent of memory. Averages or ages out over time.Lakebase-backedAgent MemoryLong-term / SemanticStores cross-conversation durable facts, user preferences, and decisions. Retrieved via semantic search to personalize future interactions. Persists independently.Lakebase-backed

---

A key innovation in the Agent Bricks ecosystem is the Memory Pipeline. Instead of adding heavy memory-writing tools directly to the agent (which can waste prompt tokens, inject background noise, or prompt the agent to write conflicting entries), the Agent Memory Pipeline operates asynchronously.

- Distillation: It automatically reads conversational logs from the session store and distills long-term facts or procedures into the main memory store.
- Consolidation: Because it runs after the fact on a schedule or on-demand, it reviews multiple conversations holistically to resolve contradictions and clean up overlapping facts.

---

The `AgentKit` SDK serves as the Databricks Python client for interacting with these agent features. It is distributed through the `databricks-agentbricks` package and hooks into your `WorkspaceClient`: bash

```
pip install databricks-agentbricks
```

Use code with caution.You can initialize a persistent long-term memory store for your agent using the following template: python

```
from databricks.sdk import WorkspaceClient
from databricks_agentkit import AgentKitClient

# Authenticate using standard Workspace credentials
client = AgentKitClient(WorkspaceClient())

# Create a managed memory store for cross-session knowledge
memory_store = client.memory_stores.create("support-agent-memory")
```

Use code with caution.For broader platform details, you can reference the Databricks Agent Bricks Product Page or walk through configuration details via the Microsoft Learn Azure Databricks Documentation. Would you like to explore:

- How to manually read and write to a memory store using Python?
- Detailed instructions for scheduling an asynchronous memory pipeline?
- How memory properties scale alongside Unity Catalog governance controls?

---

