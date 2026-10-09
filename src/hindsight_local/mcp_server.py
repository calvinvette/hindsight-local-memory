from __future__ import annotations

import json
import sys
from typing import Any

from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.paths import MemoryLocation, resolve_memory_location
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore
from hindsight_local.sync.bundles import export_sync_bundle, import_sync_bundle

SERVER_NAME = "hindsight-local-memory-mcp"
SERVER_VERSION = "0.1.0"
JSONRPC_VERSION = "2.0"
LATEST_PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2024-11-05"
LIST_TTL_MS = 60_000
LIST_CACHE_SCOPE = "public"


def _read_message() -> dict[str, Any] | None:
    content_length: int | None = None
    while True:
        header = sys.stdin.buffer.readline()
        if not header:
            return None
        if header in (b"\r\n", b"\n"):
            break
        key, _, value = header.decode("utf-8").partition(":")
        if key.lower().strip() == "content-length":
            content_length = int(value.strip())

    if content_length is None:
        return None

    payload = sys.stdin.buffer.read(content_length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def _write_message(message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=True).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def _jsonrpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _tool_text_result(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}],
        "isError": is_error,
    }


def _resolve_tool_location(arguments: dict[str, Any]) -> MemoryLocation:
    return resolve_memory_location(
        db_path=arguments.get("db_path"),
        memory_scope=arguments.get("memory_scope"),
        project_root=arguments.get("project_root"),
    )


def _tool_definitions() -> list[dict[str, Any]]:
    tools = [
        {
            "name": "memory_config",
            "description": "Resolve active memory scope and sqlite db location.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_init",
            "description": "Initialize the SQLite memory schema for a scope.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_remember",
            "description": "Ingest text memory into the selected memory scope.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_uri": {"type": "string"},
                    "title": {"type": "string"},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_search",
            "description": "Run FTS search over chunks for the selected memory scope.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_relate",
            "description": "Create a graph relation edge in the selected memory scope.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "relation": {"type": "string"},
                    "target_id": {"type": "string"},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["source_id", "relation", "target_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_export_sync",
            "description": "Export sync event bundle for the selected memory scope.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "out_path": {"type": "string"},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["out_path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_import_sync",
            "description": "Import sync event bundle into the selected memory scope.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "in_path": {"type": "string"},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["in_path"],
                "additionalProperties": False,
            },
        },
    ]
    return sorted(tools, key=lambda item: str(item.get("name", "")))


def _server_discovery_result() -> dict[str, Any]:
    return {
        "protocolVersion": LATEST_PROTOCOL_VERSION,
        "supportedProtocolVersions": [LATEST_PROTOCOL_VERSION, LEGACY_PROTOCOL_VERSION],
        "capabilities": {
            "tools": {
                "listChanged": False,
            }
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
        },
    }


def _extract_requested_protocol(request: dict[str, Any]) -> str | None:
    params = request.get("params")
    if isinstance(params, dict):
        meta = params.get("_meta")
        if isinstance(meta, dict):
            protocol = meta.get("io.modelcontextprotocol/protocolVersion")
            if isinstance(protocol, str):
                return protocol
    return None


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    location = _resolve_tool_location(arguments)
    db_path_str = str(location.db_path)

    if name == "memory_config":
        return _tool_text_result(
            {
                "memory_scope": location.memory_scope,
                "db_path": db_path_str,
                "project_root": str(location.project_root) if location.project_root else None,
            }
        )

    if name == "memory_init":
        SQLiteMemoryStore(db_path_str).init()
        return _tool_text_result(
            {
                "ok": True,
                "memory_scope": location.memory_scope,
                "db_path": db_path_str,
            }
        )

    if name == "memory_remember":
        agent = HindsightMemoryAgent(db_path_str)
        result = agent.remember(
            text=arguments["text"],
            source_uri=arguments.get("source_uri", "mcp:text"),
            title=arguments.get("title"),
        )
        return _tool_text_result({"db_path": db_path_str, "result": result})

    if name == "memory_search":
        agent = HindsightMemoryAgent(db_path_str)
        hits = agent.recall(arguments["query"], int(arguments.get("limit", 5)))
        return _tool_text_result({"db_path": db_path_str, "hits": hits})

    if name == "memory_relate":
        agent = HindsightMemoryAgent(db_path_str)
        edge = agent.relate(arguments["source_id"], arguments["relation"], arguments["target_id"])
        return _tool_text_result({"db_path": db_path_str, "edge": edge})

    if name == "memory_export_sync":
        store = SQLiteMemoryStore(db_path_str)
        out_path = str(export_sync_bundle(store, arguments["out_path"]))
        return _tool_text_result({"db_path": db_path_str, "out_path": out_path})

    if name == "memory_import_sync":
        store = SQLiteMemoryStore(db_path_str)
        imported = import_sync_bundle(store, arguments["in_path"])
        return _tool_text_result({"db_path": db_path_str, "imported": imported})

    raise ValueError(f"Unknown tool '{name}'")


def _handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    requested_protocol = _extract_requested_protocol(request)
    if requested_protocol and requested_protocol not in {
        LATEST_PROTOCOL_VERSION,
        LEGACY_PROTOCOL_VERSION,
    }:
        return _jsonrpc_error(
            request_id,
            -32602,
            (
                "Unsupported MCP protocol version "
                f"'{requested_protocol}'. Supported: {LATEST_PROTOCOL_VERSION}, {LEGACY_PROTOCOL_VERSION}"
            ),
        )

    if method == "server/discover":
        return _jsonrpc_result(request_id, _server_discovery_result())

    if method == "initialize":
        # Legacy compatibility: handshake is retired in 2026-07-28 but still accepted.
        return _jsonrpc_result(request_id, _server_discovery_result())

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return _jsonrpc_result(
            request_id,
            {
                "tools": _tool_definitions(),
                "ttlMs": LIST_TTL_MS,
                "cacheScope": LIST_CACHE_SCOPE,
            },
        )

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            return _jsonrpc_error(request_id, -32602, "tools/call requires params.name")
        try:
            return _jsonrpc_result(request_id, _call_tool(name, arguments))
        except Exception as exc:  # pragma: no cover - defensive error surface for MCP clients
            return _jsonrpc_result(
                request_id, _tool_text_result({"error": str(exc)}, is_error=True)
            )

    if request_id is None:
        return None

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    while True:
        request = _read_message()
        if request is None:
            return
        response = _handle_request(request)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    main()
