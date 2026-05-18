from __future__ import annotations

from pathlib import Path

from epo_bdds_full_text_postgres_export.io.checkpoint_store import TextFileCheckpointStore


def test_not_processed_initially(tmp_path):
    store = TextFileCheckpointStore(checkpoint_path=tmp_path / "ckpt.txt")
    assert store.has_processed("doc/ep001.xml") is False


def test_mark_processed_found(tmp_path):
    store = TextFileCheckpointStore(checkpoint_path=tmp_path / "ckpt.txt")
    store.mark_processed("doc/ep001.xml")
    assert store.has_processed("doc/ep001.xml") is True


def test_mark_processed_idempotent(tmp_path):
    ckpt = tmp_path / "ckpt.txt"
    store = TextFileCheckpointStore(checkpoint_path=ckpt)
    store.mark_processed("doc/ep001.xml")
    store.mark_processed("doc/ep001.xml")
    lines = [l for l in ckpt.read_text().splitlines() if l.strip()]
    assert lines.count("doc/ep001.xml") == 1


def test_persists_across_instances(tmp_path):
    ckpt = tmp_path / "ckpt.txt"
    store1 = TextFileCheckpointStore(checkpoint_path=ckpt)
    store1.mark_processed("doc/ep001.xml")

    store2 = TextFileCheckpointStore(checkpoint_path=ckpt)
    assert store2.has_processed("doc/ep001.xml") is True


def test_multiple_entries(tmp_path):
    store = TextFileCheckpointStore(checkpoint_path=tmp_path / "ckpt.txt")
    for i in range(5):
        store.mark_processed(f"doc/ep{i:03d}.xml")
    for i in range(5):
        assert store.has_processed(f"doc/ep{i:03d}.xml") is True
    assert store.has_processed("doc/ep999.xml") is False
