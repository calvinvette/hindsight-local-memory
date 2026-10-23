from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from hindsight_local.ids import chunk_id, document_id, hash_id
from hindsight_local.models import (
    Chunk,
    DebuggerStateCapture,
    Document,
    EditorStateCapture,
    GraphEdge,
    asdict,
    utc_now_iso,
)
from hindsight_local.paths import resolve_memory_location
from hindsight_local.sync.events import MemoryEvent

CAPTURE_SCHEMA_VERSION = "hindsight.capture.v1"
MAX_MEMORY_TEXT_CHARS = 100_000
MAX_RESULT_CHARS = 100_000
CAPTURE_TYPES = {"editor", "debugger"}


def validate_memory_input(text: Any, source_uri: Any, title: Any) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if len(text) > MAX_MEMORY_TEXT_CHARS:
        raise ValueError(f"text exceeds the {MAX_MEMORY_TEXT_CHARS} character limit")
    if not isinstance(source_uri, str) or not 1 <= len(source_uri) <= 4096:
        raise ValueError("source_uri must contain 1 to 4096 characters")
    if title is not None and (not isinstance(title, str) or len(title) > 500):
        raise ValueError("title must be a string of at most 500 characters")


def _check_max_chars(max_chars: Any) -> int | None:
    if max_chars is None:
        return None
    if type(max_chars) is not int or not 1 <= max_chars <= MAX_RESULT_CHARS:
        raise ValueError(f"max_chars must be an integer between 1 and {MAX_RESULT_CHARS}")
    return max_chars


def _check_object_id(name: str, value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 200:
        raise ValueError(f"{name} must contain 1 to 200 characters")
    return value


class SQLiteMemoryStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = resolve_memory_location(db_path=db_path).db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(context_captures)")}
            if "schema_version" not in columns:
                conn.execute(
                    "ALTER TABLE context_captures ADD COLUMN schema_version "
                    "TEXT NOT NULL DEFAULT 'hindsight.capture.v1'"
                )

    def ingest_text(
        self, text: str, source_uri: str = "local:text", title: str | None = None
    ) -> Document:
        with self.connect() as conn:
            return self._ingest_text_in_connection(conn, text, source_uri, title)

    def _ingest_text_in_connection(
        self,
        conn: sqlite3.Connection,
        text: str,
        source_uri: str,
        title: str | None,
    ) -> Document:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        doc = Document(document_id(source_uri, text), source_uri, title, content_hash)
        chunks = [
            Chunk(chunk_id(doc.doc_id, i, c), doc.doc_id, i, c)
            for i, c in enumerate(chunk_text(text))
        ]
        conn.execute(
            "INSERT OR IGNORE INTO documents VALUES (?, ?, ?, ?, ?, ?)",
            (
                doc.doc_id,
                doc.source_uri,
                doc.title,
                doc.content_hash,
                doc.created_at,
                json.dumps(doc.metadata),
            ),
        )
        conn.executemany(
            "INSERT OR IGNORE INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    c.chunk_id,
                    c.doc_id,
                    c.chunk_index,
                    c.text,
                    c.created_at,
                    json.dumps(c.metadata),
                )
                for c in chunks
            ],
        )
        self._append_event(
            conn,
            MemoryEvent.create(
                "upsert_document",
                doc.doc_id,
                {"document": doc.__dict__, "chunks": [c.__dict__ for c in chunks]},
            ),
        )
        return doc

    def search_chunks_fts(
        self, query: str, limit: int = 10, max_chars: int | None = None
    ) -> list[dict[str, Any]]:
        max_chars = _check_max_chars(max_chars)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, c.doc_id, c.text, bm25(chunks_fts) AS score
                FROM chunks_fts
                JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
                WHERE chunks_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        hits = [dict(r) for r in rows]
        if max_chars is not None:
            for hit in hits:
                if len(hit["text"]) > max_chars:
                    hit["text"] = hit["text"][:max_chars]
                    hit["text_truncated"] = True
        return hits

    def list_captures(
        self,
        capture_type: str | None = None,
        limit: int = 20,
        max_chars: int | None = 2000,
    ) -> list[dict[str, Any]]:
        if capture_type is not None and capture_type not in CAPTURE_TYPES:
            raise ValueError("capture_type must be 'editor' or 'debugger'")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        max_chars = _check_max_chars(max_chars)
        where = "WHERE capture_type = ?" if capture_type else ""
        params: list[Any] = [capture_type] if capture_type else []
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT capture_id, capture_type, captured_at, content, metadata_json, doc_id,
                       schema_version
                FROM context_captures {where}
                ORDER BY captured_at DESC, capture_id
                LIMIT ?
                """,
                [*params, limit],
            ).fetchall()
        return [self._bounded_capture(self._capture_record(row), max_chars) for row in rows]

    def get_capture(self, capture_id: str, max_chars: int | None = None) -> dict[str, Any] | None:
        _check_object_id("capture_id", capture_id)
        max_chars = _check_max_chars(max_chars)
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT capture_id, capture_type, captured_at, content, metadata_json, doc_id,
                       schema_version
                FROM context_captures WHERE capture_id = ?
                """,
                (capture_id,),
            ).fetchone()
        return self._bounded_capture(self._capture_record(row), max_chars) if row else None

    @staticmethod
    def _bounded_capture(record: dict[str, Any], max_chars: int | None) -> dict[str, Any]:
        content = record["content"]
        if max_chars is not None and content is not None and len(content) > max_chars:
            record["content"] = content[:max_chars]
            record["content_truncated"] = True
        return record

    def delete_capture(self, capture_id: str, reason: str | None = None) -> dict[str, Any]:
        _check_object_id("capture_id", capture_id)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT doc_id FROM context_captures WHERE capture_id = ?", (capture_id,)
            ).fetchone()
            if row is None:
                return {"deleted": False, "object_id": capture_id}
            conn.execute("DELETE FROM context_captures WHERE capture_id = ?", (capture_id,))
            removed = self._scrub(conn, [capture_id], [row["doc_id"]])
            self._record_forget(conn, capture_id, "capture", reason)
        return {"deleted": True, "object_id": capture_id, "removed": removed}

    def delete_document(self, doc_id: str, reason: str | None = None) -> dict[str, Any]:
        _check_object_id("doc_id", doc_id)
        with self.connect() as conn:
            if (
                conn.execute("SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
                is None
            ):
                return {"deleted": False, "object_id": doc_id}
            owner = conn.execute(
                "SELECT capture_id FROM context_captures WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            if owner is not None:
                raise ValueError(
                    f"document belongs to capture '{owner['capture_id']}'; delete the capture instead"
                )
            removed = self._scrub(conn, [], [doc_id])
            self._record_forget(conn, doc_id, "document", reason)
        return {"deleted": True, "object_id": doc_id, "removed": removed}

    def _scrub(
        self, conn: sqlite3.Connection, object_ids: list[str], doc_ids: list[str | None]
    ) -> dict[str, int]:
        """Remove derived rows and any content-bearing sync events for the given objects."""
        docs = [d for d in doc_ids if d]
        chunk_ids: list[str] = []
        if docs:
            marks = ",".join("?" for _ in docs)
            chunk_ids = [
                r["chunk_id"]
                for r in conn.execute(
                    f"SELECT chunk_id FROM chunks WHERE doc_id IN ({marks})", docs
                )
            ]
        linked = [*object_ids, *docs, *chunk_ids]
        edge_ids: list[str] = []
        if linked:
            marks = ",".join("?" for _ in linked)
            edge_ids = [
                r["edge_id"]
                for r in conn.execute(
                    f"SELECT edge_id FROM graph_edges WHERE source_id IN ({marks}) "
                    f"OR target_id IN ({marks})",
                    [*linked, *linked],
                )
            ]
        if edge_ids:
            marks = ",".join("?" for _ in edge_ids)
            conn.execute(f"DELETE FROM graph_edges WHERE edge_id IN ({marks})", edge_ids)
        if docs:
            marks = ",".join("?" for _ in docs)
            has_fallback = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'embeddings_fallback'"
            ).fetchone()
            if has_fallback:
                conn.execute(f"DELETE FROM embeddings_fallback WHERE doc_id IN ({marks})", docs)
            conn.execute(f"DELETE FROM documents WHERE doc_id IN ({marks})", docs)
        event_objects = [*object_ids, *docs, *edge_ids]
        events = 0
        if event_objects:
            marks = ",".join("?" for _ in event_objects)
            events = conn.execute(
                f"DELETE FROM sync_events WHERE json_extract(event_json, '$.object_id') IN ({marks})",
                event_objects,
            ).rowcount
        return {"chunks": len(chunk_ids), "edges": len(edge_ids), "events": events}

    def _record_forget(
        self, conn: sqlite3.Connection, object_id: str, object_type: str, reason: str | None
    ) -> None:
        if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
            raise ValueError("reason must be a string of at most 500 characters")
        conn.execute(
            "INSERT OR REPLACE INTO tombstones(object_id, object_type, reason, created_at) "
            "VALUES (?, ?, ?, ?)",
            (object_id, object_type, reason, utc_now_iso()),
        )
        self._append_event(
            conn,
            MemoryEvent.create("forget", object_id, {"object_type": object_type, "reason": reason}),
        )

    def capture_editor_state(self, capture: EditorStateCapture) -> dict[str, Any]:
        metadata = {
            "language_id": capture.language_id,
            "document_uri": capture.document_uri,
            "workspace_id": capture.workspace_id,
            "session_id": capture.session_id,
            "selection_range": (
                asdict(capture.selection_range) if capture.selection_range else None
            ),
        }
        return self._store_context_capture(
            capture_id=capture.capture_id,
            capture_type="editor",
            captured_at=capture.captured_at,
            content=capture.selected_text,
            metadata=metadata,
        )

    def capture_debugger_state(self, capture: DebuggerStateCapture) -> dict[str, Any]:
        metadata = {
            "debug_type": capture.debug_type,
            "state": capture.state,
            "session_name": capture.session_name,
            "reason": capture.reason,
            "workspace_id": capture.workspace_id,
            "session_id": capture.session_id,
            "stack_frames": [asdict(frame) for frame in capture.stack_frames],
        }
        return self._store_context_capture(
            capture_id=capture.capture_id,
            capture_type="debugger",
            captured_at=capture.captured_at,
            content=None,
            metadata=metadata,
        )

    def _store_context_capture(
        self,
        capture_id: str,
        capture_type: str,
        captured_at: str,
        content: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if capture_type not in {"editor", "debugger"}:
            raise ValueError("capture_type must be 'editor' or 'debugger'")
        if not isinstance(capture_id, str) or not capture_id or len(capture_id) > 200:
            raise ValueError("capture_id must contain 1 to 200 characters")
        if not isinstance(captured_at, str) or not captured_at or len(captured_at) > 100:
            raise ValueError("captured_at must contain 1 to 100 characters")
        if content is not None and not isinstance(content, str):
            raise ValueError("captured content must be a string")
        if content is not None and len(content) > 100_000:
            raise ValueError("captured content exceeds the 100000 character limit")
        if capture_type == "editor":
            for key, maximum in (
                ("language_id", 200),
                ("document_uri", 4096),
                ("workspace_id", 200),
                ("session_id", 200),
            ):
                value = metadata.get(key)
                if value is not None and (not isinstance(value, str) or len(value) > maximum):
                    raise ValueError(f"{key} must be a string of at most {maximum} characters")
            selection = metadata.get("selection_range")
            if selection is not None:
                if set(selection) != {
                    "start_line",
                    "start_character",
                    "end_line",
                    "end_character",
                } or any(type(value) is not int or value < 0 for value in selection.values()):
                    raise ValueError("selection_range must contain non-negative integer positions")
                if selection["end_line"] < selection["start_line"] or (
                    selection["end_line"] == selection["start_line"]
                    and selection["end_character"] < selection["start_character"]
                ):
                    raise ValueError("selection_range end must not precede its start")
        if capture_type == "debugger":
            if not isinstance(metadata.get("debug_type"), str) or not metadata["debug_type"]:
                raise ValueError("debug_type is required")
            if len(metadata["debug_type"]) > 200:
                raise ValueError("debug_type must not exceed 200 characters")
            if metadata.get("state") not in {
                "started",
                "continued",
                "stopped",
                "terminated",
                "exception",
                "unknown",
            }:
                raise ValueError("state is not a supported debugger state")
            for key, maximum in (
                ("session_name", 500),
                ("reason", 1000),
                ("workspace_id", 200),
                ("session_id", 200),
            ):
                value = metadata.get(key)
                if value is not None and (not isinstance(value, str) or len(value) > maximum):
                    raise ValueError(f"{key} must be a string of at most {maximum} characters")
            frames = metadata.get("stack_frames", [])
            if not isinstance(frames, list) or len(frames) > 100:
                raise ValueError("stack_frames must contain at most 100 frames")
            for frame in frames:
                if (
                    not isinstance(frame, dict)
                    or set(frame) - {"name", "source_uri", "line", "column"}
                    or not isinstance(frame.get("name"), str)
                    or not frame["name"]
                    or len(frame["name"]) > 500
                ):
                    raise ValueError(
                        "each stack frame must contain a valid name and supported fields"
                    )
                source_uri = frame.get("source_uri")
                if source_uri is not None and (
                    not isinstance(source_uri, str) or len(source_uri) > 4096
                ):
                    raise ValueError("stack frame source_uri must not exceed 4096 characters")
                for position in ("line", "column"):
                    value = frame.get(position)
                    if value is not None and (type(value) is not int or value < 0):
                        raise ValueError(f"stack frame {position} must be a non-negative integer")
        metadata_json = json.dumps(metadata, sort_keys=True)
        if len(metadata_json) > 64_000:
            raise ValueError("capture metadata exceeds the 64000 character limit")

        source_uri = f"vscode://{capture_type}/{capture_id}"
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT capture_id, capture_type, captured_at, content, metadata_json, doc_id,
                       schema_version
                FROM context_captures WHERE capture_id = ?
                """,
                (capture_id,),
            ).fetchone()
            if existing is not None:
                existing_record = self._capture_record(existing)
                if (
                    existing_record["capture_type"] != capture_type
                    or existing_record["content"] != content
                    or existing_record["metadata"] != metadata
                ):
                    raise ValueError("capture_id already exists with different capture data")
                return existing_record

            doc = (
                self._ingest_text_in_connection(
                    conn,
                    content,
                    source_uri=source_uri,
                    title=f"VS Code {capture_type} capture",
                )
                if content
                else None
            )
            record = {
                "capture_id": capture_id,
                "capture_type": capture_type,
                "schema_version": CAPTURE_SCHEMA_VERSION,
                "captured_at": captured_at,
                "content": content,
                "metadata": metadata,
                "doc_id": doc.doc_id if doc else None,
            }
            inserted = conn.execute(
                """
                INSERT OR IGNORE INTO context_captures
                  (capture_id, capture_type, captured_at, content, metadata_json, doc_id,
                   schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    capture_id,
                    capture_type,
                    captured_at,
                    content,
                    metadata_json,
                    doc.doc_id if doc else None,
                    CAPTURE_SCHEMA_VERSION,
                ),
            ).rowcount
            if inserted:
                self._append_event(
                    conn,
                    MemoryEvent.create(
                        f"capture_{capture_type}_state",
                        capture_id,
                        record,
                    ),
                )
                return record

            row = conn.execute(
                """
                SELECT capture_id, capture_type, captured_at, content, metadata_json, doc_id,
                       schema_version
                FROM context_captures WHERE capture_id = ?
                """,
                (capture_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("capture insert was ignored but the existing row was not found")
            return self._capture_record(row)

    @staticmethod
    def _capture_record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "capture_id": row["capture_id"],
            "capture_type": row["capture_type"],
            "schema_version": row["schema_version"],
            "captured_at": row["captured_at"],
            "content": row["content"],
            "metadata": json.loads(row["metadata_json"]),
            "doc_id": row["doc_id"],
        }

    def query_graph(
        self,
        seed_id: str | None = None,
        relation: str | None = None,
        depth: int = 1,
        limit: int = 50,
    ) -> dict[str, Any]:
        if type(depth) is not int or depth < 0 or depth > 3:
            raise ValueError("depth must be between 0 and 3")
        if type(limit) is not int or limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if seed_id is not None and (
            not isinstance(seed_id, str) or not seed_id or len(seed_id) > 200
        ):
            raise ValueError("seed_id must contain 1 to 200 characters")
        if relation is not None and (not isinstance(relation, str) or len(relation) > 200):
            raise ValueError("relation must be a string of at most 200 characters")

        edge_records: dict[str, dict[str, Any]] = {}
        visited_nodes = {seed_id} if seed_id else set()
        frontier = {seed_id} if seed_id else set()

        with self.connect() as conn:
            if seed_id:
                for _ in range(depth):
                    if not frontier or len(edge_records) >= limit:
                        break
                    placeholders = ",".join("?" for _ in frontier)
                    relation_filter = " AND relation = ?" if relation is not None else ""
                    params: list[Any] = [*frontier, *frontier]
                    if relation is not None:
                        params.append(relation)
                    params.append(limit - len(edge_records))
                    rows = conn.execute(
                        f"""
                        SELECT edge_id, source_id, relation, target_id, created_at, metadata_json
                        FROM graph_edges
                        WHERE (source_id IN ({placeholders}) OR target_id IN ({placeholders}))
                        {relation_filter}
                        ORDER BY created_at DESC, edge_id
                        LIMIT ?
                        """,
                        params,
                    ).fetchall()
                    next_frontier: set[str] = set()
                    for row in rows:
                        edge = self._edge_record(row)
                        edge_records[edge["edge_id"]] = edge
                        for node_id in (edge["source_id"], edge["target_id"]):
                            if node_id not in visited_nodes:
                                visited_nodes.add(node_id)
                                next_frontier.add(node_id)
                    frontier = next_frontier
            else:
                params = [relation] if relation is not None else []
                relation_filter = "WHERE relation = ?" if relation is not None else ""
                rows = conn.execute(
                    f"""
                    SELECT edge_id, source_id, relation, target_id, created_at, metadata_json
                    FROM graph_edges
                    {relation_filter}
                    ORDER BY created_at DESC, edge_id
                    LIMIT ?
                    """,
                    [*params, limit],
                ).fetchall()
                for row in rows:
                    edge = self._edge_record(row)
                    edge_records[edge["edge_id"]] = edge
                    visited_nodes.update((edge["source_id"], edge["target_id"]))
                capture_rows = conn.execute(
                    """
                    SELECT capture_id
                    FROM context_captures
                    ORDER BY captured_at DESC, capture_id
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                visited_nodes.update(row["capture_id"] for row in capture_rows)

            nodes = self._load_graph_nodes(conn, visited_nodes)

        return {"nodes": nodes, "edges": list(edge_records.values())}

    @staticmethod
    def _edge_record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "edge_id": row["edge_id"],
            "source_id": row["source_id"],
            "relation": row["relation"],
            "target_id": row["target_id"],
            "created_at": row["created_at"],
            "metadata": json.loads(row["metadata_json"]),
        }

    @staticmethod
    def _load_graph_nodes(conn: sqlite3.Connection, node_ids: set[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []
        ids = sorted(node_ids)
        placeholders = ",".join("?" for _ in ids)
        nodes: dict[str, dict[str, Any]] = {
            node_id: {"id": node_id, "type": "unknown"} for node_id in ids
        }

        queries = (
            (
                "documents",
                f"SELECT doc_id, source_uri, title, created_at, metadata_json FROM documents WHERE doc_id IN ({placeholders})",
            ),
            (
                "chunks",
                f"SELECT chunk_id, doc_id, text, created_at, metadata_json FROM chunks WHERE chunk_id IN ({placeholders})",
            ),
            (
                "entities",
                f"SELECT entity_id, name, kind, namespace, created_at, metadata_json FROM entities WHERE entity_id IN ({placeholders})",
            ),
            (
                "claims",
                f"SELECT claim_id, subject_id, predicate, object_value, confidence, created_at, provenance_json, qualifiers_json FROM claims WHERE claim_id IN ({placeholders})",
            ),
            (
                "context_captures",
                f"SELECT capture_id, capture_type, captured_at, content, metadata_json, doc_id, schema_version FROM context_captures WHERE capture_id IN ({placeholders})",
            ),
        )
        for table, query in queries:
            for row in conn.execute(query, ids):
                record = dict(row)
                if table in {"documents", "entities"}:
                    record["metadata"] = json.loads(record.pop("metadata_json"))
                    key = "doc_id" if table == "documents" else "entity_id"
                    node_id = record.pop(key)
                    node_type = {"documents": "document", "entities": "entity"}[table]
                elif table == "chunks":
                    record["metadata"] = json.loads(record.pop("metadata_json"))
                    node_id = record.pop("chunk_id")
                    node_type = "chunk"
                elif table == "claims":
                    record["provenance"] = json.loads(record.pop("provenance_json"))
                    record["qualifiers"] = json.loads(record.pop("qualifiers_json"))
                    node_id = record.pop("claim_id")
                    node_type = "claim"
                else:
                    record["metadata"] = json.loads(record.pop("metadata_json"))
                    node_id = record.pop("capture_id")
                    node_type = record.pop("capture_type") + "_capture"
                    if record["content"] is not None and len(record["content"]) > 2000:
                        record["content"] = record["content"][:2000]
                        record["content_truncated"] = True
                nodes[node_id] = {"id": node_id, "type": node_type, **record}
        return [nodes[node_id] for node_id in sorted(nodes)]

    def add_edge(
        self, source_id: str, relation: str, target_id: str, metadata: dict[str, Any] | None = None
    ) -> GraphEdge:
        edge = GraphEdge(
            hash_id("edge", {"s": source_id, "r": relation, "t": target_id}),
            source_id,
            relation,
            target_id,
            metadata=metadata or {},
        )
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO graph_edges VALUES (?, ?, ?, ?, ?, ?)",
                (
                    edge.edge_id,
                    edge.source_id,
                    edge.relation,
                    edge.target_id,
                    edge.created_at,
                    json.dumps(edge.metadata),
                ),
            )
            self._append_event(conn, MemoryEvent.create("link", edge.edge_id, edge.__dict__))
        return edge

    def export_events(self, since_event_id: str | None = None) -> Iterable[dict[str, Any]]:
        query = "SELECT event_json FROM sync_events ORDER BY sequence ASC"
        with self.connect() as conn:
            for row in conn.execute(query):
                yield json.loads(row["event_json"])

    def import_event(self, event: dict[str, Any]) -> None:
        # Minimal import: preserve event in local log for later projection/adjudication.
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sync_events(event_id, event_json, created_at) VALUES (?, ?, ?)",
                (
                    event["event_id"],
                    json.dumps(event, sort_keys=True),
                    event.get("ingested_at", utc_now_iso()),
                ),
            )

    def _append_event(self, conn: sqlite3.Connection, event: MemoryEvent) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO sync_events(event_id, event_json, created_at) VALUES (?, ?, ?)",
            (event.event_id, json.dumps(event.to_dict(), sort_keys=True), event.ingested_at),
        )


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs or [text]:
        if len(current) + len(p) + 1 > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n{p}".strip()
    if current:
        chunks.append(current)
    return chunks


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY,
  source_uri TEXT NOT NULL,
  title TEXT,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, text);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, chunk_id, text) VALUES (new.rowid, new.chunk_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  DELETE FROM chunks_fts WHERE rowid = old.rowid;
END;

CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  namespace TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  predicate TEXT NOT NULL,
  object_value TEXT NOT NULL,
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  provenance_json TEXT NOT NULL DEFAULT '{}',
  qualifiers_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS graph_edges (
  edge_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  target_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS context_captures (
  capture_id TEXT PRIMARY KEY,
  capture_type TEXT NOT NULL CHECK (capture_type IN ('editor', 'debugger')),
  schema_version TEXT NOT NULL DEFAULT 'hindsight.capture.v1',
  captured_at TEXT NOT NULL,
  content TEXT,
  metadata_json TEXT NOT NULL,
  doc_id TEXT REFERENCES documents(doc_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sync_events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  event_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tombstones (
  object_id TEXT PRIMARY KEY,
  object_type TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL
);
"""
