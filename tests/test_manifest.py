from __future__ import annotations

import csv
from pathlib import Path

import pytest

from epo_bdds_full_text_downloader.manifest import CsvManifest, ManifestStatus


def _manifest(tmp_path: Path, *, fixed_time: int = 1_000_000) -> CsvManifest:
    return CsvManifest(path=tmp_path / "manifest.csv", now=lambda: fixed_time)


def test_read_all_empty(tmp_path):
    m = _manifest(tmp_path)
    assert m.read_all() == {}


def test_upsert_new_entry(tmp_path):
    m = _manifest(tmp_path)
    record = {
        "filename": "ep001.zip",
        "status": "downloaded",
        "timestamp": "1000000",
        "raw_size": "512",
        "filtered_size": "",
        "final_size": "",
        "message": "",
    }
    m.upsert(record)
    rows = m.read_all()
    assert "ep001.zip" in rows
    assert rows["ep001.zip"]["status"] == "downloaded"


def test_upsert_updates_existing(tmp_path):
    m = _manifest(tmp_path)
    for status in ("downloaded", "moved"):
        m.mark("ep001.zip", ManifestStatus(status))
    rows = m.read_all()
    assert rows["ep001.zip"]["status"] == "moved"


def test_mark_sets_status(tmp_path):
    m = _manifest(tmp_path)
    m.mark("ep002.zip", ManifestStatus.DOWNLOADED)
    assert m.read_all()["ep002.zip"]["status"] == ManifestStatus.DOWNLOADED.value


def test_atomic_write_no_leftover_tmp(tmp_path):
    m = _manifest(tmp_path)
    m.mark("ep003.zip", ManifestStatus.CLEANED)
    tmp_file = m.path.with_suffix(m.path.suffix + ".tmp")
    assert not tmp_file.exists()


def test_round_trip_all_statuses(tmp_path):
    m = _manifest(tmp_path)
    for i, status in enumerate(ManifestStatus):
        m.mark(f"file_{i}.zip", status)
    rows = m.read_all()
    for i, status in enumerate(ManifestStatus):
        assert rows[f"file_{i}.zip"]["status"] == status.value


def test_multiple_files_sorted_in_csv(tmp_path):
    m = _manifest(tmp_path)
    for name in ["zz.zip", "aa.zip", "mm.zip"]:
        m.mark(name, ManifestStatus.DOWNLOADED)
    with m.path.open(newline="", encoding="utf-8") as f:
        filenames = [row["filename"] for row in csv.DictReader(f)]
    assert filenames == sorted(filenames)
