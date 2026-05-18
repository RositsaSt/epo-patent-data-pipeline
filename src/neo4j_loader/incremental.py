from __future__ import annotations

import csv
import logging
import sqlite3
from collections import defaultdict
from pathlib import Path

from neo4j import GraphDatabase

from .bulk_loader import (
    RELATIONSHIP_CSV,
    NODE_TABLE_MAP,
    _iter_batches,
    _read_csv,
)
from .config import Neo4jLoaderConfig
from .schema import ALL_CONSTRAINT_STATEMENTS

logger = logging.getLogger(__name__)


class _Neo4jCheckpoint:
    """SQLite-backed tracker of source_ids already loaded into Neo4j."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS loaded_source_ids (
                source_id  TEXT PRIMARY KEY,
                loaded_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def is_loaded(self, source_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM loaded_source_ids WHERE source_id = ? LIMIT 1",
            (source_id,),
        ).fetchone()
        return row is not None

    def mark_loaded(self, source_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO loaded_source_ids (source_id) VALUES (?)",
            (source_id,),
        )
        self._conn.commit()

    def loaded_set(self) -> set[str]:
        rows = self._conn.execute("SELECT source_id FROM loaded_source_ids").fetchall()
        return {r[0] for r in rows}

    def close(self) -> None:
        self._conn.close()


class IncrementalNeo4jUpdater:
    """
    Weekly incremental loader: reads CSVs but only MERGEs rows whose
    source_id has not yet been loaded into Neo4j.

    Uses the same batched MERGE pattern as BulkCsvLoader but filters rows
    by source_id before sending, so re-running is safe.
    """

    def __init__(self, config: Neo4jLoaderConfig) -> None:
        self._config = config
        self._driver = GraphDatabase.driver(
            config.uri, auth=(config.user, config.password)
        )
        self._checkpoint = _Neo4jCheckpoint(config.checkpoint_db)

    def close(self) -> None:
        self._driver.close()
        self._checkpoint.close()

    def __enter__(self) -> "IncrementalNeo4jUpdater":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def run(self) -> None:
        self._ensure_schema()
        already_loaded = self._checkpoint.loaded_set()
        new_source_ids = self._collect_new_source_ids(already_loaded)

        if not new_source_ids:
            logger.info("No new source_ids to load into Neo4j — skipping")
            return

        logger.info("Incrementally loading %d new source_ids into Neo4j", len(new_source_ids))
        self._load_nodes(new_source_ids)
        self._load_relationships(new_source_ids)

        for sid in new_source_ids:
            self._checkpoint.mark_loaded(sid)
        logger.info("Incremental load complete")

    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        with self._driver.session() as session:
            for stmt in ALL_CONSTRAINT_STATEMENTS:
                session.run(stmt)

    def _collect_new_source_ids(self, already_loaded: set[str]) -> set[str]:
        """Union all source_ids from all CSVs, minus already-loaded ones."""
        new_ids: set[str] = set()
        for filename in list(NODE_TABLE_MAP) + [RELATIONSHIP_CSV]:
            csv_path = self._config.csv_dir / filename
            if not csv_path.exists():
                continue
            with csv_path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    sid = row.get("source_id", "")
                    if sid and sid not in already_loaded:
                        new_ids.add(sid)
        return new_ids

    def _load_nodes(self, new_source_ids: set[str]) -> None:
        for filename, (label, merge_key) in NODE_TABLE_MAP.items():
            rows = _read_csv(self._config.csv_dir / filename)
            new_rows = [r for r in rows if r.get("source_id", "") in new_source_ids]
            if not new_rows:
                continue
            logger.info("Incrementally loading %d :%s rows", len(new_rows), label)
            cypher = (
                f"UNWIND $rows AS row "
                f"MERGE (n:{label} {{{merge_key}: row.{merge_key}}}) "
                f"SET n += row"
            )
            with self._driver.session() as session:
                for batch in _iter_batches(new_rows, self._config.batch_size):
                    session.run(cypher, rows=batch)

    def _load_relationships(self, new_source_ids: set[str]) -> None:
        rows = _read_csv(self._config.csv_dir / RELATIONSHIP_CSV)
        new_rows = [r for r in rows if r.get("source_id", "") in new_source_ids]
        if not new_rows:
            return

        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in new_rows:
            key = (
                row.get("from_label", ""),
                row.get("from_key", ""),
                row.get("rel_type", ""),
                row.get("to_label", ""),
                row.get("to_key", ""),
            )
            groups[key].append(row)

        for (from_label, from_key, rel_type, to_label, to_key), group_rows in groups.items():
            if not all([from_label, from_key, rel_type, to_label, to_key]):
                continue
            cypher = (
                f"UNWIND $rows AS row "
                f"MATCH (a:{from_label} {{{from_key}: row.from_id}}) "
                f"MATCH (b:{to_label} {{{to_key}: row.to_id}}) "
                f"MERGE (a)-[:{rel_type}]->(b)"
            )
            with self._driver.session() as session:
                for batch in _iter_batches(group_rows, self._config.batch_size):
                    session.run(cypher, rows=batch)
