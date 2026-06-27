from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from hindsight_local.ids import hash_id
from hindsight_local.storage.sqlite_store import SQLiteMemoryStore
from hindsight_local.storage.vector_store import SQLiteVecAdapter
from hindsight_local.graph.falkordb_projection import FalkorDBProjection, FalkorProjectionConfig
from hindsight_local.sync.bundles import export_sync_bundle, import_sync_bundle


class HindsightMemoryAgent:
    """Reusable façade for projects that need local Hindsight memory.

    Supports optional vector embeddings (sqlite-vec) and FalkorDB graph projection.
    """

    def __init__(
        self,
        db_path: str | Path,
        enable_vector: bool = False,
        enable_falkordb: bool = False,
        falkordb_config: Optional[FalkorProjectionConfig] = None,
    ):
        self.store = SQLiteMemoryStore(db_path)
        self.store.init()
        self.db_path = db_path
        self.vec_adapter: SQLiteVecAdapter | None = None
        self.falkordb: FalkorDBProjection | None = None

        # Optional vector embeddings
        if enable_vector:
            self.vec_adapter = SQLiteVecAdapter(str(db_path))
            self._ensure_vector_table()

        # Optional FalkorDB projection
        if enable_falkordb:
            self.falkordb = FalkorDBProjection(falkordb_config or FalkorProjectionConfig())
            self.falkordb.connect()

    def _ensure_vector_table(self) -> None:
        """Create vector table (sqlite-vec) or fallback table."""
        conn = self.store.connect()
        self.vec_adapter.ensure_vector_table(conn)
        conn.close()

    def remember(
        self,
        text: str,
        source_uri: str = "agent:note",
        title: str | None = None,
        embed: bool = True,
    ) -> dict[str, Any]:
        doc = self.store.ingest_text(text, source_uri=source_uri, title=title)
        result = {"doc_id": doc.doc_id, "source_uri": doc.source_uri, "title": doc.title}

        if embed and self.vec_adapter is not None:
            # Compute embedding (placeholder: use deterministic hash embedder for now)
            from hindsight_local.storage.vector_store import HashingEmbedder

            embedder = HashingEmbedder()
            embedding = embedder.embed(text)

            # Upsert into vector table
            conn = self.store.connect()
            self.vec_adapter.upsert_embedding_fallback(conn, doc.doc_id, doc.doc_id, embedding)
            conn.close()

        return result

    def recall(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.store.search_chunks_fts(query, limit=limit)

    def relate(self, source_id: str, relation: str, target_id: str) -> dict[str, Any]:
        edge = self.store.add_edge(source_id, relation, target_id)
        return edge.__dict__

    def export_sync(self, out_path: str | Path) -> str:
        return str(export_sync_bundle(self.store, out_path))

    def import_sync(self, in_path: str | Path) -> int:
        return import_sync_bundle(self.store, in_path)

    def project_edge(self, source_id: str, relation: str, target_id: str) -> None:
        """Project an edge into FalkorDB."""
        if self.falkordb is not None:
            self.falkordb.project_edge(source_id, relation, target_id)

    def project_document(self, doc_id: str, title: str | None = None, metadata: dict | None = None) -> None:
        """Project a document into FalkorDB."""
        if self.falkordb is not None:
            self.falkordb.project_document(doc_id, title, metadata)

    def project_claim(self, claim_id: str, subject_id: str, predicate: str, object_value: str) -> None:
        """Project a claim into FalkorDB."""
        if self.falkordb is not None:
            self.falkordb.project_claim(claim_id, subject_id, predicate, object_value)
