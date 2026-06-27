from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore


def test_ingest_and_search(tmp_path):
    agent = HindsightMemoryAgent(tmp_path / "agent-mem.db")
    agent.remember("The local memory node uses SQLite and event sourced sync.")
    hits = agent.recall("SQLite")
    assert hits


def test_default_db_name_uses_agent_mem_basename():
    store = SQLiteMemoryStore()
    assert store.db_path.name == "agent-mem.db"
