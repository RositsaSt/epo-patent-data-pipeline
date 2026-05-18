from __future__ import annotations

import csv
from pathlib import Path

from epo_bdds_full_text_graph_export.io.csv_sink import CsvAppendSink


_FIELDS = ["pub_id", "country", "pub_number"]


def _sink(tmp_path: Path) -> CsvAppendSink:
    return CsvAppendSink(csv_path=tmp_path / "out.csv", fieldnames=_FIELDS)


def test_creates_file_with_header(tmp_path):
    sink = _sink(tmp_path)
    sink.write_rows([{"pub_id": "EP1", "country": "EP", "pub_number": "001"}])
    with sink.csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == list(_FIELDS)


def test_header_written_once(tmp_path):
    sink = _sink(tmp_path)
    sink.write_rows([{"pub_id": "EP1", "country": "EP", "pub_number": "001"}])
    sink.write_rows([{"pub_id": "EP2", "country": "EP", "pub_number": "002"}])
    with sink.csv_path.open(newline="", encoding="utf-8") as f:
        lines = f.readlines()
    header_lines = [l for l in lines if l.startswith("pub_id")]
    assert len(header_lines) == 1


def test_none_values_become_empty_string(tmp_path):
    sink = _sink(tmp_path)
    sink.write_rows([{"pub_id": None, "country": "EP", "pub_number": "001"}])
    with sink.csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["pub_id"] == ""


def test_extra_keys_ignored(tmp_path):
    sink = _sink(tmp_path)
    sink.write_rows([{"pub_id": "EP1", "country": "EP", "pub_number": "1", "extra": "ignored"}])
    with sink.csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert "extra" not in (reader.fieldnames or [])


def test_returns_row_count(tmp_path):
    sink = _sink(tmp_path)
    rows = [
        {"pub_id": f"EP{i}", "country": "EP", "pub_number": str(i)}
        for i in range(3)
    ]
    count = sink.write_rows(rows)
    assert count == 3


def test_appends_across_calls(tmp_path):
    sink = _sink(tmp_path)
    sink.write_rows([{"pub_id": "EP1", "country": "EP", "pub_number": "1"}])
    sink.write_rows([{"pub_id": "EP2", "country": "EP", "pub_number": "2"}])
    with sink.csv_path.open(newline="", encoding="utf-8") as f:
        data_rows = list(csv.DictReader(f))
    assert len(data_rows) == 2
    assert data_rows[0]["pub_id"] == "EP1"
    assert data_rows[1]["pub_id"] == "EP2"
