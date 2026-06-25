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
            # conn.load_extension("vec0")  # Enable once extension path is configured.
            conn.close()
            return True
        except Exception:
            return False
