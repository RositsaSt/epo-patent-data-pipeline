from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import run_pipeline


def _configure_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pipeline_{date_str}.log"

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    logging.getLogger(__name__).info("Logging to %s", log_file)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EPO patent data pipeline orchestrator")

    parser.add_argument(
        "--mode",
        choices=["initial", "weekly"],
        required=True,
        help="'initial': first-time full bulk load. 'weekly': skip already-processed files.",
    )

    # Directory overrides (all have .env / sensible defaults)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--staging-dir", type=Path, default=None)
    parser.add_argument("--final-dir", type=Path, default=None)
    parser.add_argument("--graph-output-dir", type=Path, default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--log-dir", type=Path, default=None)

    # Neo4j overrides
    parser.add_argument("--neo4j-uri", type=str, default=None)
    parser.add_argument("--neo4j-user", type=str, default=None)
    parser.add_argument("--neo4j-password", type=str, default=None)

    return parser


def main() -> int:
    load_dotenv()
    args = build_arg_parser().parse_args()

    # Resolve directories (CLI > env > default)
    def _dir(arg_val, env_key, default) -> Path:
        raw = arg_val or os.getenv(env_key) or default
        return Path(raw).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[2]  # src/orchestrator → project root
    src_dir = project_root / "src"
    downloader_dir = src_dir / "epo_bdds_full_text_downloader"

    raw_dir      = _dir(args.raw_dir,          "PIPELINE_RAW_DIR",          "data/raw")
    staging_dir  = _dir(args.staging_dir,       "PIPELINE_STAGING_DIR",      "data/staging")
    final_dir    = _dir(args.final_dir,         "PIPELINE_FINAL_DIR",        "data/final")
    graph_dir    = _dir(args.graph_output_dir,  "PIPELINE_GRAPH_OUTPUT_DIR", "data/graph_output")
    ckpt_dir     = _dir(args.checkpoint_dir,    "PIPELINE_CHECKPOINT_DIR",   "data/checkpoints")
    log_dir      = _dir(args.log_dir,           "PIPELINE_LOG_DIR",          "logs")

    neo4j_uri      = args.neo4j_uri      or os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    neo4j_user     = args.neo4j_user     or os.getenv("NEO4J_USER",     "neo4j")
    neo4j_password = args.neo4j_password or os.getenv("NEO4J_PASSWORD", "")

    _configure_logging(log_dir)

    # Pass PYTHONPATH so subprocess stages can import src packages
    env = {**os.environ, "PYTHONPATH": str(src_dir)}

    try:
        run_pipeline(
            mode=args.mode,
            src_dir=src_dir,
            downloader_dir=downloader_dir,
            raw_dir=raw_dir,
            staging_dir=staging_dir,
            final_dir=final_dir,
            graph_output_dir=graph_dir,
            checkpoint_dir=ckpt_dir,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            env=env,
        )
    except RuntimeError as exc:
        logging.getLogger(__name__).error("Pipeline aborted: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
