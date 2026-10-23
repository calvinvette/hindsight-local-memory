from __future__ import annotations

import json
import sqlite3
import sys
from typing import Any, BinaryIO

from hindsight_local import __version__
from hindsight_local.models import (
    DebugStackFrame,
    DebuggerStateCapture,
    EditorSelectionRange,
    EditorStateCapture,
)
from hindsight_local.paths import resolve_memory_location
from hindsight_local.storage.sqlite_store import (
    MAX_MEMORY_TEXT_CHARS,
    MAX_RESULT_CHARS,
    SQLiteMemoryStore,
    validate_memory_input,
)

BRIDGE_VERSION = "hindsight.json-bridge.v1"
MAX_REQUEST_BYTES = 2 * 1024 * 1024
DEFAULT_RESULT_CHARS = 2000
LOCATION_FIELDS = {"db_path", "memory_scope", "project_root"}
METHODS = (
    "memory.capabilities",
    "memory.config",
    "memory.search",
    "memory.remember",
    "memory.relate",
    "memory.graph_query",
    "memory.capture_editor_state",
    "memory.capture_debugger_state",
    "memory.list_captures",
    "memory.get_capture",
    "memory.delete_capture",
    "memory.delete_document",
)


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

        if method == "memory.capabilities":
            _require_fields(params, set(), set())
            result = {
                "bridge_version": BRIDGE_VERSION,
                "package_version": __version__,
                "methods": list(METHODS),
                "limits": {
                    "max_request_bytes": MAX_REQUEST_BYTES,
                    "max_memory_text_chars": MAX_MEMORY_TEXT_CHARS,
                    "max_result_chars": MAX_RESULT_CHARS,
                    "default_result_chars": DEFAULT_RESULT_CHARS,
                },
            }
        elif method == "memory.config":
            _require_fields(params, LOCATION_FIELDS, set())
            result = {
                "memory_scope": location.memory_scope,
                "db_path": str(location.db_path),
                "project_root": str(location.project_root) if location.project_root else None,
            }
        elif method == "memory.search":
            _require_fields(
                params,
                {"query", "limit", "max_chars", *LOCATION_FIELDS},
                {"query"},
            )
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            limit = params.get("limit", 5)
            if type(limit) is not int or not 1 <= limit <= 100:
                raise ValueError("limit must be an integer between 1 and 100")
            if not isinstance(params["query"], str) or not params["query"]:
                raise ValueError("query must be a non-empty string")
            result = {
                "hits": store.search_chunks_fts(
                    params["query"],
                    limit=limit,
                    max_chars=params.get("max_chars", DEFAULT_RESULT_CHARS),
                )
            }
        elif method == "memory.remember":
            _require_fields(params, {"text", "source_uri", "title", *LOCATION_FIELDS}, {"text"})
            source_uri = params.get("source_uri", "bridge:text")
            title = params.get("title")
            validate_memory_input(params["text"], source_uri, title)
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            doc = store.ingest_text(params["text"], source_uri=source_uri, title=title)
            result = {"doc_id": doc.doc_id, "source_uri": doc.source_uri, "title": doc.title}
        elif method == "memory.relate":
            _require_fields(
                params,
                {"source_id", "relation", "target_id", *LOCATION_FIELDS},
                {"source_id", "relation", "target_id"},
            )
            for field_name in ("source_id", "relation", "target_id"):
                value = params[field_name]
                if not isinstance(value, str) or not 1 <= len(value) <= 200:
                    raise ValueError(f"{field_name} must contain 1 to 200 characters")
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            edge = store.add_edge(params["source_id"], params["relation"], params["target_id"])
            result = {"edge": edge.__dict__}
        elif method == "memory.list_captures":
            _require_fields(params, {"capture_type", "limit", "max_chars", *LOCATION_FIELDS}, set())
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = {
                "captures": store.list_captures(
                    capture_type=params.get("capture_type"),
                    limit=params.get("limit", 20),
                    max_chars=params.get("max_chars", DEFAULT_RESULT_CHARS),
                )
            }
        elif method == "memory.get_capture":
            _require_fields(params, {"capture_id", "max_chars", *LOCATION_FIELDS}, {"capture_id"})
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = {
                "capture": store.get_capture(
                    params["capture_id"], max_chars=params.get("max_chars", DEFAULT_RESULT_CHARS)
                )
            }
        elif method == "memory.delete_capture":
            _require_fields(params, {"capture_id", "reason", *LOCATION_FIELDS}, {"capture_id"})
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = store.delete_capture(params["capture_id"], reason=params.get("reason"))
        elif method == "memory.delete_document":
            _require_fields(params, {"doc_id", "reason", *LOCATION_FIELDS}, {"doc_id"})
            store = SQLiteMemoryStore(location.db_path)
            store.init()
            result = store.delete_document(params["doc_id"], reason=params.get("reason"))
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


def read_request_line(
    stream: BinaryIO, limit: int = MAX_REQUEST_BYTES
) -> tuple[bytes | None, bool]:
    """Return (line, oversized); line is None at EOF. Oversized lines are drained, not kept."""
    line = stream.readline(limit + 1)
    if not line:
        return None, False
    if len(line) <= limit or line.endswith(b"\n"):
        return line, False
    while True:
        chunk = stream.readline(65536)
        if not chunk or chunk.endswith(b"\n"):
            return b"", True


def main() -> None:
    while True:
        raw, oversized = read_request_line(sys.stdin.buffer)
        if raw is None:
            return
        request_id: Any = None
        if oversized:
            response = {
                "version": BRIDGE_VERSION,
                "id": None,
                "error": {"message": f"request exceeds {MAX_REQUEST_BYTES} bytes"},
            }
        elif not raw.strip():
            continue
        else:
            try:
                request = json.loads(raw.decode("utf-8"))
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
