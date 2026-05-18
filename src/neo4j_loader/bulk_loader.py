from __future__ import annotations

import csv
import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from neo4j import GraphDatabase

from .config import Neo4jLoaderConfig
from .schema import ALL_CONSTRAINT_STATEMENTS

logger = logging.getLogger(__name__)

# Maps CSV filename → (Neo4j label, merge key property)
NODE_TABLE_MAP: dict[str, tuple[str, str]] = {
    "nodes_publication.csv":             ("Publication",       "pub_id"),
    "nodes_application.csv":             ("Application",       "appln_id"),
    "nodes_ipc_classification.csv":      ("IpcClassification", "ipc_long_code"),
    "nodes_cpc_classification.csv":      ("CpcClassification", "cpc_long_code"),
    "nodes_applicant.csv":               ("Applicant",         "org_key"),
    "nodes_inventor.csv":                ("Inventor",          "person_key"),
    "nodes_attorney_representative.csv": ("Attorney",          "person_key"),
    "nodes_source_files.csv":            ("SourceFile",        "source_id"),
}

RELATIONSHIP_CSV = "relationships.csv"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        logger.warning("CSV not found, skipping: %s", path)
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _iter_batches(rows: list[dict], batch_size: int) -> Iterator[list[dict]]:
    for i in range(0, len(rows), batch_size):
        yield rows[i : i + batch_size]


class BulkCsvLoader:
    """
    Loads graph-export CSVs into Neo4j using batched MERGE via the Python driver.

    Idempotent: MERGE semantics mean re-running is safe.
    """

    def __init__(self, config: Neo4jLoaderConfig) -> None:
        self._config = config
        self._driver = GraphDatabase.driver(
            config.uri, auth=(config.user, config.password)
        )

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "BulkCsvLoader":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def setup_schema(self) -> None:
        logger.info("Creating Neo4j constraints and indexes")
        with self._driver.session() as session:
            for stmt in ALL_CONSTRAINT_STATEMENTS:
                session.run(stmt)
        logger.info("Schema setup complete")

    def load_nodes(self) -> None:
        for filename, (label, merge_key) in NODE_TABLE_MAP.items():
            csv_path = self._config.csv_dir / filename
            rows = _read_csv(csv_path)
            if not rows:
                continue
            logger.info("Loading %d rows into :%s from %s", len(rows), label, filename)
            self._merge_nodes(label, merge_key, rows)
            logger.info("Done loading :%s", label)

    def load_relationships(self) -> None:
        csv_path = self._config.csv_dir / RELATIONSHIP_CSV
        rows = _read_csv(csv_path)
        if not rows:
            return

        # Group by relationship shape so each batch runs the same Cypher template
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in rows:
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
                logger.warning("Skipping malformed relationship rows (missing fields)")
                continue
            logger.info(
                "Loading %d :%s relationships (%s→%s)",
                len(group_rows), rel_type, from_label, to_label,
            )
            self._merge_relationships(
                from_label, from_key, rel_type, to_label, to_key, group_rows
            )

    def run_all(self) -> None:
        self.setup_schema()
        self.load_nodes()
        self.load_relationships()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _merge_nodes(self, label: str, merge_key: str, rows: list[dict]) -> None:
        cypher = (
            f"UNWIND $rows AS row "
            f"MERGE (n:{label} {{{merge_key}: row.{merge_key}}}) "
            f"SET n += row"
        )
        with self._driver.session() as session:
            for batch in _iter_batches(rows, self._config.batch_size):
                session.run(cypher, rows=batch)

    def _merge_relationships(
        self,
        from_label: str,
        from_key: str,
        rel_type: str,
        to_label: str,
        to_key: str,
        rows: list[dict],
    ) -> None:
        cypher = (
            f"UNWIND $rows AS row "
            f"MATCH (a:{from_label} {{{from_key}: row.from_id}}) "
            f"MATCH (b:{to_label} {{{to_key}: row.to_id}}) "
            f"MERGE (a)-[:{rel_type}]->(b)"
        )
        with self._driver.session() as session:
            for batch in _iter_batches(rows, self._config.batch_size):
                session.run(cypher, rows=batch)
