from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .bulk_loader import BulkCsvLoader
from .config import Neo4jLoaderConfig
from .incremental import IncrementalNeo4jUpdater


logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load graph-export CSVs into Neo4j")

    parser.add_argument(
        "--mode",
        choices=["initial", "incremental"],
        default="initial",
        help="'initial': full bulk load (idempotent). 'incremental': only load new source_ids.",
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=None,
        help="Directory containing graph-export CSVs (overrides PIPELINE_GRAPH_OUTPUT_DIR env var).",
    )
    parser.add_argument("--neo4j-uri", type=str, default=None)
    parser.add_argument("--neo4j-user", type=str, default=None)
    parser.add_argument("--neo4j-password", type=str, default=None)
    parser.add_argument(
        "--checkpoint-db",
        type=Path,
        default=None,
        help="Path to Neo4j loader checkpoint SQLite DB (incremental mode only).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
    )
    parser.add_argument(
        "--step",
        choices=["schema", "nodes", "relationships", "all"],
        default="all",
        help="For initial mode: which step(s) to run.",
    )

    return parser


def main() -> int:
    load_dotenv()

    args = build_arg_parser().parse_args()

    csv_dir = args.csv_dir or Path(
        os.getenv("PIPELINE_GRAPH_OUTPUT_DIR", "data/graph_output")
    )
    neo4j_uri = args.neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = args.neo4j_user or os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = args.neo4j_password or os.getenv("NEO4J_PASSWORD", "")
    checkpoint_db = args.checkpoint_db or Path(
        os.getenv("PIPELINE_CHECKPOINT_DIR", "data/checkpoints")
    ) / "neo4j_loader_checkpoint.sqlite"

    config = Neo4jLoaderConfig(
        uri=neo4j_uri,
        user=neo4j_user,
        password=neo4j_password,
        csv_dir=csv_dir.expanduser().resolve(),
        batch_size=args.batch_size,
        checkpoint_db=checkpoint_db,
    )

    if args.mode == "initial":
        with BulkCsvLoader(config) as loader:
            step = args.step
            if step in ("schema", "all"):
                loader.setup_schema()
            if step in ("nodes", "all"):
                loader.load_nodes()
            if step in ("relationships", "all"):
                loader.load_relationships()
    else:
        with IncrementalNeo4jUpdater(config) as updater:
            updater.run()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
