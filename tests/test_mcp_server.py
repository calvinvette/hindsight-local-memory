from __future__ import annotations

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
