from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any

from hindsight_local.models import (
    DebugStackFrame,
    DebuggerStateCapture,
    EditorSelectionRange,
    EditorStateCapture,
)
from hindsight_local.paths import resolve_memory_location
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore

BRIDGE_VERSION = "hindsight.json-bridge.v1"


def handle_request(request: Any) -> dict[str, Any]:
    request_id = request.get("id") if isinstance(request, dict) else None
    try:
        if not isinstance(request, dict):
            raise ValueError("request must be a JSON object")
        method = request.get("method")
        params = request.get("params", {})
        if not isinstance(method, str):
            raise ValueError("request.method must be a string")
        if not isinstance(params, dict):
            raise ValueError("request.params must be an object")

        allowed_envelope_fields = {"id", "method", "params", "version"}
        if set(request) - allowed_envelope_fields:
            raise ValueError("unexpected request envelope fields")
        requested_version = request.get("version")
        if requested_version is not None and requested_version != BRIDGE_VERSION:
            raise ValueError(f"unsupported bridge version '{requested_version}'")

        location_args = {
            key: params[key] for key in ("db_path", "memory_scope", "project_root") if key in params
        }
        location = resolve_memory_location(**location_args)

        if method == "memory.config":
            _require_fields(params, {"db_path", "memory_scope", "project_root"}, set())
            result = {
                "memory_scope": location.memory_scope,
                "db_path": str(location.db_path),
                "project_root": str(location.project_root) if location.project_root else None,
            }
        elif method == "memory.search":
            _require_fields(
                params,
                {"query", "limit", "db_path", "memory_scope", "project_root"},
                {"query"},
            )
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            limit = params.get("limit", 5)
            if type(limit) is not int or not 1 <= limit <= 100:
                raise ValueError("limit must be an integer between 1 and 100")
            if not isinstance(params["query"], str) or not params["query"]:
                raise ValueError("query must be a non-empty string")
            result = {"hits": store.search_chunks_fts(params["query"], limit=limit)}
        elif method == "memory.graph_query":
            _require_fields(
                params,
                {
                    "seed_id",
                    "relation",
                    "depth",
                    "limit",
                    "db_path",
                    "memory_scope",
                    "project_root",
                },
                set(),
            )
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = store.query_graph(
                seed_id=params.get("seed_id"),
                relation=params.get("relation"),
                depth=params.get("depth", 1),
                limit=params.get("limit", 50),
            )
        elif method == "memory.capture_editor_state":
            _require_fields(
                params,
                {
                    "capture_id",
                    "captured_at",
                    "language_id",
                    "document_uri",
                    "workspace_id",
                    "session_id",
                    "selection_range",
                    "selected_text",
                    "db_path",
                    "memory_scope",
                    "project_root",
                },
                set(),
            )
            editor_fields: dict[str, Any] = {
                key: params[key]
                for key in (
                    "capture_id",
                    "captured_at",
                    "language_id",
                    "document_uri",
                    "workspace_id",
                    "session_id",
                    "selected_text",
                )
                if key in params
            }
            selection = params.get("selection_range")
            if selection is not None:
                if not isinstance(selection, dict):
                    raise ValueError("selection_range must be an object")
                _require_fields(
                    selection,
                    {"start_line", "start_character", "end_line", "end_character"},
                    {"start_line", "start_character", "end_line", "end_character"},
                )
                editor_fields["selection_range"] = EditorSelectionRange(**selection)
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = {"capture": store.capture_editor_state(EditorStateCapture(**editor_fields))}
        elif method == "memory.capture_debugger_state":
            _require_fields(
                params,
                {
                    "capture_id",
                    "captured_at",
                    "debug_type",
                    "state",
                    "session_name",
                    "reason",
                    "workspace_id",
                    "session_id",
                    "stack_frames",
                    "db_path",
                    "memory_scope",
                    "project_root",
                },
                {"debug_type", "state"},
            )
            debugger_fields: dict[str, Any] = {
                key: params[key]
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
                if key in params
            }
            stack_frames = params.get("stack_frames", [])
            if not isinstance(stack_frames, list):
                raise ValueError("stack_frames must be an array")
            debugger_fields["stack_frames"] = []
            for frame in stack_frames:
                if not isinstance(frame, dict):
                    raise ValueError("each stack frame must be an object")
                _require_fields(
                    frame,
                    {"name", "source_uri", "line", "column"},
                    {"name"},
                )
                debugger_fields["stack_frames"].append(DebugStackFrame(**frame))
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = {
                "capture": store.capture_debugger_state(DebuggerStateCapture(**debugger_fields))
            }
        else:
            raise ValueError(f"unknown method '{method}'")
        return {"version": BRIDGE_VERSION, "id": request_id, "result": result}
    except (KeyError, TypeError, ValueError, OSError, sqlite3.Error) as exc:
        return {
            "version": BRIDGE_VERSION,
            "id": request_id,
            "error": {"message": str(exc)},
        }


def _require_fields(value: dict[str, Any], allowed: set[str], required: set[str]) -> None:
    if not isinstance(value, dict):
        raise ValueError("value must be an object")
    unexpected = set(value) - allowed
    missing = required - set(value)
    if unexpected:
        raise ValueError(f"unexpected fields: {', '.join(sorted(unexpected))}")
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id: Any = None
        try:
            request = json.loads(line)
            if isinstance(request, dict):
                request_id = request.get("id")
            response = handle_request(request)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            response = {
                "version": BRIDGE_VERSION,
                "id": request_id,
                "error": {"message": f"invalid JSON: {exc}"},
            }
        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
