from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FalkorProjectionConfig:
    graph_name: str = "hindsight"
    host: str = "localhost"
    port: int = 6379


class FalkorDBProjection:
    """Optional graph projection target.

    SQLite remains the authoritative store. This class should project entities, claims, chunks, and
    edges into FalkorDB/FalkorDB Lite for Cypher-style traversal.
    """

    def __init__(self, config: FalkorProjectionConfig):
        self.config = config
        self._graph = None

    def connect(self) -> None:
        try:
            from falkordb import FalkorDB
        except ImportError as exc:
            raise RuntimeError("Install with `pip install -e .[falkordb]` to enable FalkorDB projection.") from exc
        db = FalkorDB(host=self.config.host, port=self.config.port)
        self._graph = db.select_graph(self.config.graph_name)

    def project_edge(self, source_id: str, relation: str, target_id: str) -> None:
        if self._graph is None:
            self.connect()
        assert self._graph is not None
        query = """
        MERGE (s:MemoryObject {id: $source_id})
        MERGE (t:MemoryObject {id: $target_id})
        MERGE (s)-[:RELATED {relation: $relation}]->(t)
        """
        self._graph.query(query, {"source_id": source_id, "target_id": target_id, "relation": relation})
