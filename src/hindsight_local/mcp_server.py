from __future__ import annotations

import json
import sys
from typing import Any

from hindsight_local.agent.memory_agent import HindsightMemoryAgent
from hindsight_local.models import (
    DebugStackFrame,
    DebuggerStateCapture,
    EditorSelectionRange,
    EditorStateCapture,
)
from hindsight_local.paths import MemoryLocation, resolve_memory_location
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore, validate_memory_input
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


def _validate_tool_arguments(
    arguments: dict[str, Any], allowed: set[str], required: set[str]
) -> None:
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    unexpected = set(arguments) - allowed
    missing = required - set(arguments)
    if unexpected:
        raise ValueError(f"unexpected arguments: {', '.join(sorted(unexpected))}")
    if missing:
        raise ValueError(f"missing required arguments: {', '.join(sorted(missing))}")


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
                    "max_chars": {"type": "integer", "minimum": 1, "maximum": 100000},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_graph_query",
            "description": (
                "Run a bounded, read-only graph traversal over local HLM nodes and edges. "
                "Provide a seed_id to expand neighbors, or omit it to return recent edges."
            ),
            "annotations": {"readOnlyHint": True},
            "inputSchema": {
                "type": "object",
                "properties": {
                    "seed_id": {"type": "string", "maxLength": 200},
                    "relation": {"type": "string", "maxLength": 200},
                    "depth": {"type": "integer", "minimum": 0, "maximum": 3, "default": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_capture_editor_state",
            "description": (
                "Persist explicitly approved VS Code editor metadata and optional selected text "
                "as a typed local HLM capture. Do not pass unreviewed file contents."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "capture_id": {"type": "string", "maxLength": 200},
                    "language_id": {"type": "string", "maxLength": 200},
                    "document_uri": {"type": "string", "maxLength": 4096},
                    "workspace_id": {"type": "string", "maxLength": 200},
                    "session_id": {"type": "string", "maxLength": 200},
                    "selection_range": {
                        "type": "object",
                        "properties": {
                            "start_line": {"type": "integer", "minimum": 0},
                            "start_character": {"type": "integer", "minimum": 0},
                            "end_line": {"type": "integer", "minimum": 0},
                            "end_character": {"type": "integer", "minimum": 0},
                        },
                        "required": [
                            "start_line",
                            "start_character",
                            "end_line",
                            "end_character",
                        ],
                        "additionalProperties": False,
                    },
                    "selected_text": {"type": "string", "maxLength": 100000},
                    "captured_at": {"type": "string", "maxLength": 100},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "memory_capture_debugger_state",
            "description": (
                "Persist explicitly approved debugger session metadata and stack frames as a "
                "typed local HLM capture. Do not include variable values, expressions, or "
                "debug-console contents."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "capture_id": {"type": "string", "maxLength": 200},
                    "debug_type": {"type": "string", "minLength": 1, "maxLength": 200},
                    "state": {
                        "type": "string",
                        "enum": [
                            "started",
                            "continued",
                            "stopped",
                            "terminated",
                            "exception",
                            "unknown",
                        ],
                    },
                    "session_name": {"type": "string", "maxLength": 500},
                    "reason": {"type": "string", "maxLength": 1000},
                    "workspace_id": {"type": "string", "maxLength": 200},
                    "session_id": {"type": "string", "maxLength": 200},
                    "stack_frames": {
                        "type": "array",
                        "maxItems": 100,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "minLength": 1, "maxLength": 500},
                                "source_uri": {"type": "string", "maxLength": 4096},
                                "line": {"type": "integer", "minimum": 0},
                                "column": {"type": "integer", "minimum": 0},
                            },
                            "required": ["name"],
                            "additionalProperties": False,
                        },
                    },
                    "captured_at": {"type": "string", "maxLength": 100},
                    "memory_scope": {"type": "string", "enum": ["project", "global"]},
                    "project_root": {"type": "string"},
                    "db_path": {"type": "string"},
                },
                "required": ["debug_type", "state"],
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
        validate_memory_input(
            arguments.get("text"), arguments.get("source_uri", "mcp:text"), arguments.get("title")
        )
        agent = HindsightMemoryAgent(db_path_str)
        result = agent.remember(
            text=arguments["text"],
            source_uri=arguments.get("source_uri", "mcp:text"),
            title=arguments.get("title"),
        )
        return _tool_text_result({"db_path": db_path_str, "result": result})

    if name == "memory_search":
        store = SQLiteMemoryStore(db_path_str)
        store.init()
        hits = store.search_chunks_fts(
            arguments["query"],
            int(arguments.get("limit", 5)),
            max_chars=arguments.get("max_chars"),
        )
        return _tool_text_result({"db_path": db_path_str, "hits": hits})

    if name == "memory_graph_query":
        _validate_tool_arguments(
            arguments,
            {
                "seed_id",
                "relation",
                "depth",
                "limit",
                "memory_scope",
                "project_root",
                "db_path",
            },
            set(),
        )
        store = SQLiteMemoryStore(db_path_str)
        store.init()
        graph = store.query_graph(
            seed_id=arguments.get("seed_id"),
            relation=arguments.get("relation"),
            depth=arguments.get("depth", 1),
            limit=arguments.get("limit", 50),
        )
        return _tool_text_result({"db_path": db_path_str, **graph})

    if name == "memory_capture_editor_state":
        allowed_fields = {
            "capture_id",
            "language_id",
            "document_uri",
            "workspace_id",
            "session_id",
            "selection_range",
            "selected_text",
            "captured_at",
            "memory_scope",
            "project_root",
            "db_path",
        }
        _validate_tool_arguments(arguments, allowed_fields, set())
        capture_fields = {
            key: arguments[key]
            for key in (
                "capture_id",
                "captured_at",
                "language_id",
                "document_uri",
                "workspace_id",
                "session_id",
                "selected_text",
            )
            if key in arguments
        }
        range_data = arguments.get("selection_range")
        if range_data is not None:
            capture_fields["selection_range"] = EditorSelectionRange(**range_data)
        editor_capture = EditorStateCapture(**capture_fields)
        store = SQLiteMemoryStore(db_path_str)
        store.init()
        result = store.capture_editor_state(editor_capture)
        return _tool_text_result({"db_path": db_path_str, "capture": result})

    if name == "memory_capture_debugger_state":
        allowed_fields = {
            "capture_id",
            "debug_type",
            "state",
            "session_name",
            "reason",
            "workspace_id",
            "session_id",
            "stack_frames",
            "captured_at",
            "memory_scope",
            "project_root",
            "db_path",
        }
        _validate_tool_arguments(arguments, allowed_fields, {"debug_type", "state"})
        capture_fields = {
            key: arguments[key]
            for key in (
                "capture_id",
                "captured_at",
                "debug_type",
                "state",
                "session_name",
                "reason",
                "workspace_id",
                "session_id",
            )
            if key in arguments
        }
        capture_fields["stack_frames"] = [
            DebugStackFrame(**frame) for frame in arguments.get("stack_frames", [])
        ]
        debugger_capture = DebuggerStateCapture(**capture_fields)
        store = SQLiteMemoryStore(db_path_str)
        store.init()
        result = store.capture_debugger_state(debugger_capture)
        return _tool_text_result({"db_path": db_path_str, "capture": result})

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
