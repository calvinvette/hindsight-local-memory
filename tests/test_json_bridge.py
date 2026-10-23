from __future__ import annotations

from hindsight_local.json_bridge import BRIDGE_VERSION, handle_request


def test_json_bridge_graph_and_editor_capture(tmp_path) -> None:
    db_path = str(tmp_path / "bridge.db")
    capture = handle_request(
        {
            "id": 1,
            "method": "memory.capture_editor_state",
            "params": {
                "db_path": db_path,
                "capture_id": "bridge-editor-1",
                "language_id": "python",
                "selected_text": "bridge editor capture sentinel",
            },
        }
    )
    assert capture["id"] == 1
    assert capture["version"] == BRIDGE_VERSION
    capture_id = capture["result"]["capture"]["capture_id"]

    graph = handle_request(
        {
            "id": 2,
            "method": "memory.graph_query",
            "params": {"db_path": db_path, "seed_id": capture_id},
        }
    )
    assert graph["id"] == 2
    assert graph["result"]["nodes"][0]["type"] == "editor_capture"


def test_json_bridge_debug_capture_is_typed(tmp_path) -> None:
    result = handle_request(
        {
            "id": "debug",
            "method": "memory.capture_debugger_state",
            "params": {
                "db_path": str(tmp_path / "bridge-debug.db"),
                "debug_type": "python",
                "state": "exception",
                "stack_frames": [
                    {"name": "main", "source_uri": "file:///workspace/main.py", "line": 10}
                ],
            },
        }
    )

    capture = result["result"]["capture"]
    assert capture["capture_type"] == "debugger"
    assert capture["metadata"]["stack_frames"][0]["line"] == 10


def test_json_bridge_rejects_unexpected_or_malformed_requests() -> None:
    unexpected = handle_request(
        {
            "id": 3,
            "method": "memory.graph_query",
            "params": {"raw_query": "MATCH (n) RETURN n"},
        }
    )
    malformed = handle_request(["not", "an", "object"])
    wrong_version = handle_request(
        {"id": 4, "version": "unsupported", "method": "memory.config", "params": {}}
    )

    assert "error" in unexpected
    assert "unexpected fields" in unexpected["error"]["message"]
    assert malformed["error"]["message"] == "request must be a JSON object"
    assert "unsupported bridge version" in wrong_version["error"]["message"]


def test_json_bridge_config_does_not_create_database_directory(tmp_path) -> None:
    target = tmp_path / "not-created" / "memory.db"
    result = handle_request(
        {"id": 5, "method": "memory.config", "params": {"db_path": str(target)}}
    )

    assert result["result"]["db_path"] == str(target)
    assert not target.parent.exists()
