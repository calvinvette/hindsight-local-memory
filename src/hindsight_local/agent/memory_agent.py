from __future__ import annotations

from pathlib import Path
from typing import Any

from hindsight_local.storage.sqlite_store import SQLiteMemoryStore
from hindsight_local.sync.bundles import export_sync_bundle, import_sync_bundle


class HindsightMemoryAgent:
    """Reusable façade for projects that need local Hindsight memory."""

    def __init__(self, db_path: str | Path):
        self.store = SQLiteMemoryStore(db_path)
        self.store.init()

    def remember(self, text: str, source_uri: str = "agent:note", title: str | None = None) -> dict[str, Any]:
        doc = self.store.ingest_text(text, source_uri=source_uri, title=title)
        return {"doc_id": doc.doc_id, "source_uri": doc.source_uri, "title": doc.title}

    def recall(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return self.store.search_chunks_fts(query, limit=limit)

    def relate(self, source_id: str, relation: str, target_id: str) -> dict[str, Any]:
        edge = self.store.add_edge(source_id, relation, target_id)
        return edge.__dict__

    def export_sync(self, out_path: str | Path) -> str:
        return str(export_sync_bundle(self.store, out_path))

    def import_sync(self, in_path: str | Path) -> int:
        return import_sync_bundle(self.store, in_path)
