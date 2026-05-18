from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from epo_bdds_full_text_graph_export.io.checkpoint_store import ProcessedXmlCheckpointStore


def _store(tmp_path: Path) -> ProcessedXmlCheckpointStore:
    return ProcessedXmlCheckpointStore(db_path=tmp_path / "checkpoint.sqlite")


def test_new_source_id_not_done(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    assert store.is_done(conn, "doc/ep001.xml") is False
    conn.close()


def test_mark_done_then_is_done(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    store.mark_done(conn, "doc/ep001.xml")
    conn.commit()
    assert store.is_done(conn, "doc/ep001.xml") is True
    conn.close()


def test_mark_done_idempotent(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    store.mark_done(conn, "doc/ep001.xml")
    store.mark_done(conn, "doc/ep001.xml")  # second call must not raise
    conn.commit()
    conn.close()


def test_mark_failed_stores_error(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    store.mark_failed(conn, "doc/ep002.xml", "SomeError: bad xml")
    conn.commit()
    row = conn.execute(
        "SELECT status, error FROM processed_xml WHERE source_id = ?",
        ("doc/ep002.xml",),
    ).fetchone()
    assert row[0] == "failed"
    assert "SomeError" in row[1]
    conn.close()


def test_upsert_failed_then_done(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    store.mark_failed(conn, "doc/ep003.xml", "oops")
    store.mark_done(conn, "doc/ep003.xml")
    conn.commit()
    assert store.is_done(conn, "doc/ep003.xml") is True
    conn.close()


def test_invalid_source_id_none_raises(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    with pytest.raises(ValueError):
        store.is_done(conn, None)  # type: ignore[arg-type]
    conn.close()


def test_invalid_source_id_blank_raises(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    with pytest.raises(ValueError):
        store.mark_done(conn, "   ")
    conn.close()


def test_record_failure_safely_with_none_source_id(tmp_path):
    store = _store(tmp_path)
    conn = store.open_connection()
    # Must not raise even with None source_id
    store.record_failure_safely(conn, None, "some error")  # type: ignore[arg-type]
    conn.commit()
    conn.close()


def test_error_normalization_none():
    result = ProcessedXmlCheckpointStore._norm_error(None)
    assert result == ""


def test_error_normalization_truncates():
    long_error = "x" * 5000
    result = ProcessedXmlCheckpointStore._norm_error(long_error)
    assert len(result) == 2000
