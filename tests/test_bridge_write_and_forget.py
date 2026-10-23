from __future__ import annotations

import io
import sqlite3

from hindsight_local.json_bridge import (
    BRIDGE_VERSION,
    METHODS,
    handle_request,
    read_request_line,
)


def call(db: str, method: str, **params):
    return handle_request({"id": 1, "method": method, "params": {"db_path": db, **params}})


def event_blob(db: str) -> str:
    with sqlite3.connect(db) as conn:
        return "\n".join(row[0] for row in conn.execute("SELECT event_json FROM sync_events"))


def test_capabilities_lists_every_handled_method() -> None:
    caps = handle_request({"id": 1, "method": "memory.capabilities", "params": {}})["result"]
    assert caps["bridge_version"] == BRIDGE_VERSION
    assert caps["methods"] == list(METHODS)
    for method in METHODS:
        response = handle_request({"id": 1, "method": method, "params": {"bogus": 1}})
        assert "unknown method" not in response["error"]["message"]


def test_remember_search_truncation_and_document_delete(tmp_path) -> None:
    db = str(tmp_path / "m.db")
    remembered = call(db, "memory.remember", text="zebra " * 600, title="t")["result"]
    hits = call(db, "memory.search", query="zebra", max_chars=50)["result"]["hits"]
    assert hits and hits[0]["text_truncated"] is True and len(hits[0]["text"]) == 50

    deleted = call(db, "memory.delete_document", doc_id=remembered["doc_id"], reason="test")
    assert deleted["result"]["deleted"] is True
    assert call(db, "memory.search", query="zebra")["result"]["hits"] == []
    assert "zebra" not in event_blob(db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT reason FROM tombstones").fetchone()[0] == "test"
    assert (
        call(db, "memory.delete_document", doc_id=remembered["doc_id"])["result"]["deleted"]
        is False
    )


def test_capture_list_get_delete_scrubs_derived_data(tmp_path) -> None:
    db = str(tmp_path / "c.db")
    call(
        db,
        "memory.capture_editor_state",
        capture_id="cap-1",
        language_id="python",
        selected_text="quokka selection " * 300,
    )
    call(db, "memory.relate", source_id="cap-1", relation="mentions", target_id="entity-1")

    listed = call(db, "memory.list_captures", capture_type="editor", max_chars=20)["result"]
    assert [c["capture_id"] for c in listed["captures"]] == ["cap-1"]
    assert listed["captures"][0]["content_truncated"] is True
    assert call(db, "memory.get_capture", capture_id="cap-1")["result"]["capture"]

    # A capture's document cannot be deleted independently of the capture.
    doc_id = call(db, "memory.get_capture", capture_id="cap-1")["result"]["capture"]["doc_id"]
    assert "capture" in call(db, "memory.delete_document", doc_id=doc_id)["error"]["message"]

    removed = call(db, "memory.delete_capture", capture_id="cap-1")["result"]
    assert removed["deleted"] is True and removed["removed"]["edges"] == 1
    assert call(db, "memory.get_capture", capture_id="cap-1")["result"]["capture"] is None
    assert call(db, "memory.search", query="quokka")["result"]["hits"] == []
    assert "quokka" not in event_blob(db)
    assert call(db, "memory.graph_query", seed_id="entity-1")["result"]["edges"] == []


def test_remember_and_relate_validate_input(tmp_path) -> None:
    db = str(tmp_path / "v.db")
    too_long = call(db, "memory.remember", text="x" * 100_001)
    blank = call(db, "memory.remember", text="   ")
    bad_edge = call(db, "memory.relate", source_id="a", relation="", target_id="b")
    extra = call(db, "memory.remember", text="ok", unexpected=True)
    assert "character limit" in too_long["error"]["message"]
    assert "non-empty" in blank["error"]["message"]
    assert "relation" in bad_edge["error"]["message"]
    assert "unexpected fields" in extra["error"]["message"]


def test_request_line_reader_rejects_and_drains_oversized_lines() -> None:
    stream = io.BytesIO(b"x" * 50 + b"\n" + b'{"ok":1}\n' + b"y" * 20)
    line, oversized = read_request_line(stream, limit=10)
    assert oversized is True
    assert read_request_line(stream, limit=10) == (b'{"ok":1}\n', False)
    assert read_request_line(stream, limit=100) == (b"y" * 20, False)
    assert read_request_line(stream, limit=10) == (None, False)
