from __future__ import annotations

import json
from pathlib import Path

from hindsight_local.storage.sqlite_store import SQLiteMemoryStore


def export_sync_bundle(store: SQLiteMemoryStore, out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in store.export_events():
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def import_sync_bundle(store: SQLiteMemoryStore, in_path: str | Path) -> int:
    count = 0
    with Path(in_path).open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                store.import_event(json.loads(line))
                count += 1
    return count
