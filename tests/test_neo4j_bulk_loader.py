from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from neo4j_loader.bulk_loader import BulkCsvLoader, _iter_batches, _read_csv
from neo4j_loader.config import Neo4jLoaderConfig


def _config(tmp_path: Path) -> Neo4jLoaderConfig:
    return Neo4jLoaderConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
        csv_dir=tmp_path,
        batch_size=5,
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# _read_csv
# ---------------------------------------------------------------------------

def test_read_csv_returns_rows(tmp_path):
    p = tmp_path / "test.csv"
    _write_csv(p, ["a", "b"], [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])
    rows = _read_csv(p)
    assert len(rows) == 2
    assert rows[0]["a"] == "1"


def test_read_csv_missing_file_returns_empty(tmp_path):
    rows = _read_csv(tmp_path / "nonexistent.csv")
    assert rows == []


# ---------------------------------------------------------------------------
# _iter_batches
# ---------------------------------------------------------------------------

def test_iter_batches_splits_correctly():
    rows = list(range(11))
    batches = list(_iter_batches(rows, 5))
    assert len(batches) == 3
    assert batches[0] == [0, 1, 2, 3, 4]
    assert batches[1] == [5, 6, 7, 8, 9]
    assert batches[2] == [10]


def test_iter_batches_empty_input():
    assert list(_iter_batches([], 5)) == []


# ---------------------------------------------------------------------------
# BulkCsvLoader (mocked driver)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_loader(tmp_path, mocker):
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    mocker.patch("neo4j_loader.bulk_loader.GraphDatabase.driver", return_value=mock_driver)
    loader = BulkCsvLoader(_config(tmp_path))
    return loader, mock_session, mock_driver


def test_load_nodes_skips_missing_csvs(mock_loader):
    loader, mock_session, _ = mock_loader
    loader.load_nodes()  # no CSVs present — must not raise
    mock_session.run.assert_not_called()


def test_load_nodes_calls_merge(tmp_path, mock_loader):
    loader, mock_session, _ = mock_loader
    pub_csv = tmp_path / "nodes_publication.csv"
    _write_csv(pub_csv, ["pub_id", "country", "pub_number", "kind_code",
                          "publication_date", "pub_language", "source_id"],
               [{"pub_id": "EP1", "country": "EP", "pub_number": "1",
                 "kind_code": "A1", "publication_date": "20240101",
                 "pub_language": "en", "source_id": "src1"}])
    loader.load_nodes()
    assert mock_session.run.called
    call_args = mock_session.run.call_args_list[0]
    cypher = call_args[0][0]
    assert "MERGE" in cypher
    assert "Publication" in cypher


def test_load_relationships_groups_by_type(tmp_path, mock_loader):
    loader, mock_session, _ = mock_loader
    rel_csv = tmp_path / "relationships.csv"
    _write_csv(rel_csv,
               ["from_label", "from_key", "from_id", "rel_type",
                "to_label", "to_key", "to_id", "source_id"],
               [
                   {"from_label": "Publication", "from_key": "pub_id",
                    "from_id": "EP1", "rel_type": "HAS_IPC",
                    "to_label": "IpcClassification", "to_key": "ipc_long_code",
                    "to_id": "G06F1/00", "source_id": "src1"},
                   {"from_label": "Publication", "from_key": "pub_id",
                    "from_id": "EP2", "rel_type": "HAS_CPC",
                    "to_label": "CpcClassification", "to_key": "cpc_long_code",
                    "to_id": "H04L1/00", "source_id": "src2"},
               ])
    loader.load_relationships()
    # Two different rel_types → two separate session.run calls
    assert mock_session.run.call_count == 2


def test_context_manager_closes_driver(tmp_path, mocker):
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    mocker.patch("neo4j_loader.bulk_loader.GraphDatabase.driver", return_value=mock_driver)
    with BulkCsvLoader(_config(tmp_path)):
        pass
    mock_driver.close.assert_called_once()
