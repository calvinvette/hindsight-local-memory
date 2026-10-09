from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore


def test_ingest_and_search(tmp_path):
    agent = HindsightMemoryAgent(tmp_path / "agent-mem.db")
    agent.remember("The local memory node uses SQLite and event sourced sync.")
    hits = agent.recall("SQLite")
    assert hits


def test_default_db_name_uses_agent_mem_basename(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HINDSIGHT_DB", raising=False)
    monkeypatch.delenv("HINDSIGHT_MEMORY_SCOPE", raising=False)
    store = SQLiteMemoryStore()
    assert store.db_path.name == "agent-mem.db"


def test_default_db_path_is_project_local(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HINDSIGHT_DB", raising=False)
    monkeypatch.delenv("HINDSIGHT_MEMORY_SCOPE", raising=False)
    store = SQLiteMemoryStore()
    assert store.db_path == (tmp_path / ".hindsight" / "agent-mem.db").resolve()
