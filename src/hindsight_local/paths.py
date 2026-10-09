from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB_BASENAME = "agent-mem.db"
DEFAULT_SCOPE = "project"
_VALID_SCOPES = {"project", "global"}


@dataclass(frozen=True)
class MemoryLocation:
    memory_scope: str
    db_path: Path
    project_root: Path | None


def resolve_memory_location(
    db_path: str | Path | None = None,
    memory_scope: str | None = None,
    project_root: str | Path | None = None,
) -> MemoryLocation:
    """Resolve memory location from explicit args, env vars, and defaults."""
    if db_path is not None:
        resolved = Path(db_path).expanduser().resolve()
        return MemoryLocation(
            memory_scope=_normalize_scope(
                memory_scope or os.environ.get("HINDSIGHT_MEMORY_SCOPE") or DEFAULT_SCOPE
            ),
            db_path=resolved,
            project_root=_project_root_or_none(project_root),
        )

    env_db = os.environ.get("HINDSIGHT_DB")
    if env_db:
        resolved = Path(env_db).expanduser().resolve()
        return MemoryLocation(
            memory_scope=_normalize_scope(
                memory_scope or os.environ.get("HINDSIGHT_MEMORY_SCOPE") or DEFAULT_SCOPE
            ),
            db_path=resolved,
            project_root=_project_root_or_none(project_root),
        )

    scope = _normalize_scope(
        memory_scope or os.environ.get("HINDSIGHT_MEMORY_SCOPE") or DEFAULT_SCOPE
    )
    if scope == "global":
        home = Path(os.environ.get("HINDSIGHT_GLOBAL_HOME", Path.home() / ".hindsight"))
        return MemoryLocation(
            memory_scope=scope, db_path=home / DEFAULT_DB_BASENAME, project_root=None
        )

    root = _resolve_project_root(project_root)
    return MemoryLocation(
        memory_scope=scope,
        db_path=root / ".hindsight" / DEFAULT_DB_BASENAME,
        project_root=root,
    )


def _normalize_scope(value: str) -> str:
    scope = value.strip().lower()
    if scope not in _VALID_SCOPES:
        raise ValueError(
            f"Invalid memory scope '{value}'. Expected one of: {sorted(_VALID_SCOPES)}"
        )
    return scope


def _resolve_project_root(project_root: str | Path | None) -> Path:
    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    env_root = os.environ.get("HINDSIGHT_PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path.cwd().resolve()


def _project_root_or_none(project_root: str | Path | None) -> Path | None:
    if project_root is None and not os.environ.get("HINDSIGHT_PROJECT_ROOT"):
        return None
    return _resolve_project_root(project_root)
