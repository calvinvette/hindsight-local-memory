from __future__ import annotations

import json

from hindsight_local import mcp_server


def test_server_discover_returns_latest_protocol() -> None:
    request = {"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {}}
    response = mcp_server._handle_request(request)
    assert response is not None
    result = response["result"]
    assert result["protocolVersion"] == "2026-07-28"
    assert "2026-07-28" in result["supportedProtocolVersions"]


def test_tools_list_includes_cache_hints() -> None:
    request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    response = mcp_server._handle_request(request)
    assert response is not None
    result = response["result"]
    assert "tools" in result
    assert result["ttlMs"] == 60000
    assert result["cacheScope"] == "public"


def test_legacy_initialize_still_works() -> None:
    request = {"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}}
    response = mcp_server._handle_request(request)
    assert response is not None
    assert response["result"]["protocolVersion"] == "2026-07-28"


def test_unknown_protocol_version_rejected() -> None:
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/list",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2099-01-01",
            }
        },
    }
    response = mcp_server._handle_request(request)
    assert response is not None
    assert response["error"]["code"] == -32602


def test_tools_list_exposes_graph_and_typed_capture_tools() -> None:
    request = {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": {}}
    response = mcp_server._handle_request(request)
    assert response is not None
    tools = {tool["name"]: tool for tool in response["result"]["tools"]}

    assert tools["memory_graph_query"]["annotations"]["readOnlyHint"] is True
    assert "selection_range" in tools["memory_capture_editor_state"]["inputSchema"]["properties"]
    assert "stack_frames" in tools["memory_capture_debugger_state"]["inputSchema"]["properties"]
    assert "Do not include variable values" in tools["memory_capture_debugger_state"]["description"]


def _call_tool(name: str, arguments: dict) -> dict:
    response = mcp_server._handle_request(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    assert response is not None
    return json.loads(response["result"]["content"][0]["text"])


def test_mcp_editor_capture_and_graph_query(tmp_path) -> None:
    database = str(tmp_path / "mcp-memory.db")
    capture_result = _call_tool(
        "memory_capture_editor_state",
        {
            "capture_id": "mcp-editor-1",
            "language_id": "typescript",
            "document_uri": "file:///workspace/app.ts",
            "selection_range": {
                "start_line": 1,
                "start_character": 0,
                "end_line": 2,
                "end_character": 10,
            },
            "selected_text": "MCP editor capture searchable marker",
            "db_path": database,
        },
    )
    assert capture_result["capture"]["capture_type"] == "editor"

    graph_result = _call_tool(
        "memory_graph_query",
        {"seed_id": capture_result["capture"]["capture_id"], "db_path": database},
    )
    assert graph_result["nodes"][0]["type"] == "editor_capture"


def test_mcp_debugger_capture_rejects_unknown_fields(tmp_path) -> None:
    result = _call_tool(
        "memory_capture_debugger_state",
        {
            "debug_type": "python",
            "state": "stopped",
            "variables": [{"name": "secret", "value": "not-allowed"}],
            "db_path": str(tmp_path / "mcp-memory.db"),
        },
    )
    assert "error" in result
    assert "unexpected arguments" in result["error"]
