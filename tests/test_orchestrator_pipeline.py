from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orchestrator.pipeline import _run, run_pipeline


# ---------------------------------------------------------------------------
# _run helper
# ---------------------------------------------------------------------------

def test_run_success(mocker):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mocker.patch("orchestrator.pipeline.subprocess.run", return_value=mock_result)
    _run("test-stage", ["echo", "hello"])  # must not raise


def test_run_failure_raises(mocker):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mocker.patch("orchestrator.pipeline.subprocess.run", return_value=mock_result)
    with pytest.raises(RuntimeError, match="test-stage"):
        _run("test-stage", ["false"])


# ---------------------------------------------------------------------------
# run_pipeline — subprocess call count and arguments
# ---------------------------------------------------------------------------

def _pipeline_kwargs(tmp_path: Path, mode: str) -> dict:
    return dict(
        mode=mode,
        src_dir=tmp_path / "src",
        downloader_dir=tmp_path / "src" / "epo_bdds_full_text_downloader",
        raw_dir=tmp_path / "raw",
        staging_dir=tmp_path / "staging",
        final_dir=tmp_path / "final",
        graph_output_dir=tmp_path / "graph",
        checkpoint_dir=tmp_path / "checkpoints",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        env={},
    )


def test_initial_mode_calls_all_four_stages(tmp_path, mocker):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("orchestrator.pipeline.subprocess.run", return_value=mock_result)
    run_pipeline(**_pipeline_kwargs(tmp_path, "initial"))
    assert mock_run.call_count == 4


def test_weekly_mode_uses_incremental_neo4j(tmp_path, mocker):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("orchestrator.pipeline.subprocess.run", return_value=mock_result)
    run_pipeline(**_pipeline_kwargs(tmp_path, "weekly"))
    # 4th call is Neo4j loader; check --mode incremental is in its args
    fourth_call_args = mock_run.call_args_list[3][0][0]
    assert "--mode" in fourth_call_args
    idx = fourth_call_args.index("--mode")
    assert fourth_call_args[idx + 1] == "incremental"


def test_initial_mode_uses_bulk_neo4j(tmp_path, mocker):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run = mocker.patch("orchestrator.pipeline.subprocess.run", return_value=mock_result)
    run_pipeline(**_pipeline_kwargs(tmp_path, "initial"))
    fourth_call_args = mock_run.call_args_list[3][0][0]
    idx = fourth_call_args.index("--mode")
    assert fourth_call_args[idx + 1] == "initial"


def test_stage_failure_aborts_pipeline(tmp_path, mocker):
    failing = MagicMock()
    failing.returncode = 1
    mock_run = mocker.patch("orchestrator.pipeline.subprocess.run", return_value=failing)
    with pytest.raises(RuntimeError):
        run_pipeline(**_pipeline_kwargs(tmp_path, "initial"))
    assert mock_run.call_count == 1  # aborted after first failure
