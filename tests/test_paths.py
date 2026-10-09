from __future__ import annotations

from hindsight_local.paths import resolve_memory_location


def test_resolve_memory_location_prefers_explicit_db_path(tmp_path):
    explicit = tmp_path / "custom.db"
    location = resolve_memory_location(db_path=explicit)
    assert location.db_path == explicit.resolve()


def test_resolve_memory_location_uses_env_db(monkeypatch, tmp_path):
    env_db = tmp_path / "from-env.db"
    monkeypatch.setenv("HINDSIGHT_DB", str(env_db))
    location = resolve_memory_location()
    assert location.db_path == env_db.resolve()


def test_resolve_memory_location_defaults_to_project_scope(monkeypatch, tmp_path):
    monkeypatch.delenv("HINDSIGHT_DB", raising=False)
    monkeypatch.delenv("HINDSIGHT_MEMORY_SCOPE", raising=False)
    monkeypatch.chdir(tmp_path)

    location = resolve_memory_location()
    assert location.memory_scope == "project"
    assert location.project_root == tmp_path.resolve()
    assert location.db_path == (tmp_path / ".hindsight" / "agent-mem.db").resolve()


def test_resolve_memory_location_global_scope(monkeypatch, tmp_path):
    global_home = tmp_path / "global-home"
    monkeypatch.delenv("HINDSIGHT_DB", raising=False)
    monkeypatch.setenv("HINDSIGHT_MEMORY_SCOPE", "global")
    monkeypatch.setenv("HINDSIGHT_GLOBAL_HOME", str(global_home))

    location = resolve_memory_location()
    assert location.memory_scope == "global"
    assert location.project_root is None
    assert location.db_path == (global_home / "agent-mem.db").resolve()


def test_resolve_memory_location_uses_project_root_env(monkeypatch, tmp_path):
    project_root = tmp_path / "proj"
    monkeypatch.delenv("HINDSIGHT_DB", raising=False)
    monkeypatch.setenv("HINDSIGHT_MEMORY_SCOPE", "project")
    monkeypatch.setenv("HINDSIGHT_PROJECT_ROOT", str(project_root))

    location = resolve_memory_location()
    assert location.memory_scope == "project"
    assert location.project_root == project_root.resolve()
    assert location.db_path == (project_root / ".hindsight" / "agent-mem.db").resolve()
