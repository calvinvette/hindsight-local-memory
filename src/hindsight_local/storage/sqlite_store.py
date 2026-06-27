from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from hindsight_local.ids import chunk_id, document_id, hash_id
from hindsight_local.models import Chunk, Document, GraphEdge, utc_now_iso
from hindsight_local.sync.events import MemoryEvent


class SQLiteMemoryStore:
    def __init__(self, db_path: str | Path | None = None):
        # Precedence: explicit argument > HINDSIGHT_DB env var > default 'agent-mem.db'
        if db_path is None:
            env_db = os.environ.get("HINDSIGHT_DB")
            db_path = env_db if env_db else "agent-mem.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def ingest_text(self, text: str, source_uri: str = "local:text", title: str | None = None) -> Document:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        doc = Document(document_id(source_uri, text), source_uri, title, content_hash)
        chunks = [Chunk(chunk_id(doc.doc_id, i, c), doc.doc_id, i, c) for i, c in enumerate(chunk_text(text))]
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO documents VALUES (?, ?, ?, ?, ?, ?)",
                (doc.doc_id, doc.source_uri, doc.title, doc.content_hash, doc.created_at, json.dumps(doc.metadata)),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
                [(c.chunk_id, c.doc_id, c.chunk_index, c.text, c.created_at, json.dumps(c.metadata)) for c in chunks],
            )
            self._append_event(conn, MemoryEvent.create("upsert_document", doc.doc_id, {"document": doc.__dict__, "chunks": [c.__dict__ for c in chunks]}))
        return doc

    def search_chunks_fts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
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
            return [dict(r) for r in rows]

    def add_edge(self, source_id: str, relation: str, target_id: str, metadata: dict[str, Any] | None = None) -> GraphEdge:
        edge = GraphEdge(hash_id("edge", {"s": source_id, "r": relation, "t": target_id}), source_id, relation, target_id, metadata=metadata or {})
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO graph_edges VALUES (?, ?, ?, ?, ?, ?)",
                (edge.edge_id, edge.source_id, edge.relation, edge.target_id, edge.created_at, json.dumps(edge.metadata)),
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
                (event["event_id"], json.dumps(event, sort_keys=True), event.get("ingested_at", utc_now_iso())),
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
