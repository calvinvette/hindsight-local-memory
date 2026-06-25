from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Document:
    doc_id: str
    source_uri: str
    title: str | None
    content_hash: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    chunk_index: int
    text: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Entity:
    entity_id: str
    name: str
    kind: str = "entity"
    namespace: str = "default"
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Claim:
    claim_id: str
    subject_id: str
    predicate: str
    object_value: str
    confidence: float = 0.5
    created_at: str = field(default_factory=utc_now_iso)
    provenance: dict[str, Any] = field(default_factory=dict)
    qualifiers: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source_id: str
    relation: str
    target_id: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


def to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
