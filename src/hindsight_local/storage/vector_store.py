from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Embedder(Protocol):
    model_id: str

    def embed(self, text: str) -> list[float]: ...


@dataclass
class HashingEmbedder:
    """Tiny deterministic fallback embedder for tests and demos.

    Replace this with a real local embedding model adapter. This is not semantically strong, but it keeps
    the project runnable without external dependencies.
    """

    model_id: str = "hashing-demo-v1"
    dimensions: int = 128

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in text.lower().split():
            idx = hash(token) % self.dimensions
            vec[idx] += 1.0
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]


class SQLiteVecAdapter:
    """Placeholder adapter for sqlite-vec.

    Keep this isolated because sqlite-vec APIs may change. Pin the sqlite-vec version and implement
    extension loading plus vec table DDL here.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def available(self) -> bool:
        try:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            conn.enable_load_extension(True)
            # Try loading common extension names; this is platform-dependent.
            try:
                conn.load_extension("vec0")
            except Exception:
                try:
                    conn.load_extension("mod_vec")
                except Exception:
                    # extension may be built-in or not present; availability will be judged by import/runtime
                    pass
            conn.close()
            return True
        except Exception:
            return False

    def ensure_vector_table(self, conn, table_name: str = "embeddings", dims: int = 1536) -> None:
        """Create a vector table using sqlite-vec when available. Fall back to a JSON blob table otherwise."""
        cur = conn.cursor()
        try:
            # Example DDL for sqlite-vec; actual DDL depends on the extension version.
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id TEXT PRIMARY KEY, doc_id TEXT, vec VECTOR({dims}))")
            conn.commit()
        except Exception:
            # Fallback: store embeddings as JSON text
            cur.execute(
                "CREATE TABLE IF NOT EXISTS embeddings_fallback (id TEXT PRIMARY KEY, doc_id TEXT, embedding_json TEXT)"
            )
            conn.commit()

    def upsert_embedding_fallback(self, conn, id: str, doc_id: str, embedding: list[float]) -> None:
        import json

        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO embeddings_fallback (id, doc_id, embedding_json) VALUES (?, ?, ?)",
            (id, doc_id, json.dumps(embedding)),
        )
        conn.commit()

    def knn_search_fallback(self, conn, query_vec: list[float], k: int = 5) -> list[tuple[str, float]]:
        """Naive in-Python cosine similarity search over fallback embeddings."""
        import json
        import math

        cur = conn.cursor()
        rows = cur.execute("SELECT id, doc_id, embedding_json FROM embeddings_fallback").fetchall()
        def cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a)) or 1.0
            nb = math.sqrt(sum(x * x for x in b)) or 1.0
            return dot / (na * nb)

        scored = []
        for r in rows:
            emb = json.loads(r[2])
            scored.append((r[1], cos(query_vec, emb)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
