from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_id(namespace: str, payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return f"{namespace}_{digest[:32]}"


def document_id(source_uri: str, content: str) -> str:
    return hash_id("doc", {"source_uri": source_uri, "content_hash": hashlib.sha256(content.encode()).hexdigest()})


def chunk_id(doc_id: str, chunk_index: int, text: str) -> str:
    return hash_id("chunk", {"doc_id": doc_id, "chunk_index": chunk_index, "text": normalize_text(text)})


def entity_id(namespace: str, name: str, kind: str = "entity") -> str:
    return hash_id("ent", {"namespace": namespace, "kind": kind, "name": normalize_text(name)})


def claim_id(subject_id: str, predicate: str, object_value: str, qualifiers: dict[str, Any] | None = None) -> str:
    return hash_id("claim", {"s": subject_id, "p": predicate, "o": normalize_text(object_value), "q": qualifiers or {}})


def embedding_id(chunk_id_value: str, embedding_model_id: str) -> str:
    return hash_id("emb", {"chunk_id": chunk_id_value, "model": embedding_model_id})
