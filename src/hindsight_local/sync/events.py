from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

from hindsight_local.ids import hash_id
from hindsight_local.models import utc_now_iso


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    unit_id: str
    actor_id: str
    operation: str
    object_id: str
    payload: dict[str, Any]
    observed_at: str
    ingested_at: str
    schema_version: str = "hindsight.local.v1"
    parent_event_ids: list[str] = field(default_factory=list)
    signature: str | None = None

    @classmethod
    def create(
        cls,
        operation: str,
        object_id: str,
        payload: dict[str, Any],
        unit_id: str = "local-unit",
        actor_id: str = "local-agent",
        parent_event_ids: list[str] | None = None,
    ) -> "MemoryEvent":
        observed_at = utc_now_iso()
        ingested_at = utc_now_iso()
        event_payload = {
            "unit_id": unit_id,
            "actor_id": actor_id,
            "operation": operation,
            "object_id": object_id,
            "payload": payload,
            "observed_at": observed_at,
            "parent_event_ids": parent_event_ids or [],
        }
        return cls(
            event_id=hash_id("evt", event_payload),
            unit_id=unit_id,
            actor_id=actor_id,
            operation=operation,
            object_id=object_id,
            payload=payload,
            observed_at=observed_at,
            ingested_at=ingested_at,
            parent_event_ids=parent_event_ids or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
