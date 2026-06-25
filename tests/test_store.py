from hindsight_local.agent.memory_agent import HindsightMemoryAgent


def test_ingest_and_search(tmp_path):
    agent = HindsightMemoryAgent(tmp_path / "hindsight.db")
    agent.remember("The local memory node uses SQLite and event sourced sync.")
    hits = agent.recall("SQLite")
    assert hits
