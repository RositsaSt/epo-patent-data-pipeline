from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


def _run(label: str, cmd: list[str], *, cwd: Path | None = None, env=None) -> None:
    """Run a subprocess stage and raise on failure."""
    logger.info("[%s] Starting: %s", label, " ".join(str(c) for c in cmd))
    t0 = time.monotonic()
    result = subprocess.run(cmd, cwd=cwd, env=env)
    elapsed = time.monotonic() - t0
    if result.returncode != 0:
        logger.error("[%s] FAILED (exit %d) after %.1fs", label, result.returncode, elapsed)
        raise RuntimeError(f"Stage '{label}' failed with exit code {result.returncode}")
    logger.info("[%s] Done in %.1fs", label, elapsed)


def run_pipeline(
    *,
    mode: Literal["initial", "weekly"],
    src_dir: Path,
    downloader_dir: Path,
    raw_dir: Path,
    staging_dir: Path,
    final_dir: Path,
    graph_output_dir: Path,
    checkpoint_dir: Path,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    env: dict,
) -> None:
    """
    Runs all pipeline stages in sequence:
      1. Download (BDDS downloader)
      2. Graph CSV export
      3. PostgreSQL full-text export
      4. Neo4j load (bulk for 'initial', incremental for 'weekly')
    """
    python = sys.executable
    neo4j_checkpoint = checkpoint_dir / "neo4j_loader_checkpoint.sqlite"
    pg_checkpoint = checkpoint_dir / "postgres_fulltext_checkpoint.txt"
    graph_checkpoint_dir = graph_output_dir / "checkpoint"

    # ── Stage 1: Download ───────────────────────────────────────────────────
    _run(
        "download",
        [
            python, "main.py",
            "--raw-dir", str(raw_dir),
            "--staging-dir", str(staging_dir),
            "--final-dir", str(final_dir),
            "-v",
        ],
        cwd=downloader_dir,
    )

    # ── Stage 2: Graph CSV export ───────────────────────────────────────────
    _run(
        "graph-export",
        [
            python, "-m", "epo_bdds_full_text_graph_export.cli",
            "--archives-dir", str(final_dir),
            "--output-dir", str(graph_output_dir),
        ],
        cwd=src_dir,
        env=env,
    )

    # ── Stage 3: PostgreSQL full-text export ────────────────────────────────
    _run(
        "postgres-export",
        [
            python, "-m", "epo_bdds_full_text_postgres_export.cli",
            "--archives-dir", str(final_dir),
            "--checkpoint", str(pg_checkpoint),
        ],
        cwd=src_dir,
        env=env,
    )

    # ── Stage 4: Neo4j load ─────────────────────────────────────────────────
    neo4j_mode = "initial" if mode == "initial" else "incremental"
    _run(
        "neo4j-load",
        [
            python, "-m", "neo4j_loader.cli",
            "--mode", neo4j_mode,
            "--csv-dir", str(graph_output_dir),
            "--neo4j-uri", neo4j_uri,
            "--neo4j-user", neo4j_user,
            "--neo4j-password", neo4j_password,
            "--checkpoint-db", str(neo4j_checkpoint),
        ],
        cwd=src_dir,
        env=env,
    )
