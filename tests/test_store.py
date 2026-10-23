import sqlite3

from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.models import (
    DebugStackFrame,
    DebuggerStateCapture,
    EditorSelectionRange,
    EditorStateCapture,
)
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


def test_graph_query_returns_bounded_neighbors_and_node_details(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "graph.db")
    store.init()
    document = store.ingest_text("A local graph query can follow memory relationships.")
    store.add_edge(document.doc_id, "references", "entity-1")
    store.add_edge("entity-1", "related_to", "entity-2")

    first_hop = store.query_graph(seed_id=document.doc_id, depth=1)
    assert len(first_hop["edges"]) == 1
    assert first_hop["edges"][0]["relation"] == "references"
    assert any(node["type"] == "document" for node in first_hop["nodes"])

    second_hop = store.query_graph(seed_id=document.doc_id, depth=2)
    assert len(second_hop["edges"]) == 2
    assert (
        store.query_graph(seed_id=document.doc_id, depth=3, limit=1)["edges"] == first_hop["edges"]
    )


def test_editor_capture_is_typed_searchable_and_idempotent(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "capture.db")
    store.init()
    capture = EditorStateCapture(
        capture_id="capture-editor-1",
        language_id="python",
        document_uri="file:///workspace/main.py",
        workspace_id="workspace-1",
        selection_range=EditorSelectionRange(2, 4, 3, 8),
        selected_text="HLM editor capture searchable sentinel",
    )

    first = store.capture_editor_state(capture)
    repeated = store.capture_editor_state(
        EditorStateCapture(
            capture_id="capture-editor-1",
            captured_at="later-retry",
            language_id="python",
            document_uri="file:///workspace/main.py",
            workspace_id="workspace-1",
            selection_range=EditorSelectionRange(2, 4, 3, 8),
            selected_text="HLM editor capture searchable sentinel",
        )
    )

    assert first == repeated
    assert first["capture_type"] == "editor"
    assert first["schema_version"] == "hindsight.capture.v1"
    assert first["doc_id"]
    assert store.search_chunks_fts("sentinel")[0]["doc_id"] == first["doc_id"]
    node = store.query_graph(seed_id=capture.capture_id)["nodes"][0]
    assert node["type"] == "editor_capture"
    assert node["metadata"]["language_id"] == "python"
    assert any(item["id"] == capture.capture_id for item in store.query_graph()["nodes"])


def test_capture_id_collision_with_different_content_is_rejected(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "capture-collision.db")
    store.init()
    store.capture_editor_state(
        EditorStateCapture(capture_id="same-id", selected_text="first selection")
    )

    try:
        store.capture_editor_state(
            EditorStateCapture(capture_id="same-id", selected_text="different selection")
        )
    except ValueError as exc:
        assert "different capture data" in str(exc)
    else:
        raise AssertionError("capture ID collision should be rejected")


def test_debugger_capture_stores_stack_frames_without_variable_values(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "debugger.db")
    store.init()
    capture = DebuggerStateCapture(
        capture_id="capture-debug-1",
        debug_type="python",
        state="stopped",
        reason="breakpoint",
        stack_frames=[
            DebugStackFrame(
                name="calculate",
                source_uri="file:///workspace/main.py",
                line=12,
                column=3,
            )
        ],
    )

    saved = store.capture_debugger_state(capture)

    assert saved["capture_type"] == "debugger"
    assert saved["content"] is None
    assert saved["metadata"]["stack_frames"][0]["name"] == "calculate"
    assert "variables" not in saved["metadata"]


def test_graph_query_rejects_out_of_bounds_limits(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "limits.db")
    store.init()

    for kwargs in ({"depth": 4}, {"limit": 101}, {"seed_id": ""}):
        try:
            store.query_graph(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"query_graph should reject {kwargs}")


def test_init_adds_capture_schema_version_to_older_capture_table(tmp_path):
    database = tmp_path / "old-capture-schema.db"
    with sqlite3.connect(database) as conn:
        conn.execute(
            """
            CREATE TABLE context_captures (
              capture_id TEXT PRIMARY KEY,
              capture_type TEXT NOT NULL,
              captured_at TEXT NOT NULL,
              content TEXT,
              metadata_json TEXT NOT NULL,
              doc_id TEXT
            )
            """
        )

    store = SQLiteMemoryStore(database)
    store.init()
    capture = store.capture_debugger_state(
        DebuggerStateCapture(capture_id="migrated", debug_type="python", state="stopped")
    )

    assert capture["schema_version"] == "hindsight.capture.v1"
