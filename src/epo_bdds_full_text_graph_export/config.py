from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class OutputTables:
    publications_csv: Path
    applications_csv: Path
    persons_csv: Path
    citations_csv: Path
    relationships_csv: Path


@dataclass(frozen=True)
class CsvSchemas:
    publications_fields: Sequence[str]
    applications_fields: Sequence[str]
    persons_fields: Sequence[str]
    citations_fields: Sequence[str]
    relationships_fields: Sequence[str]


@dataclass(frozen=True)
class ExportConfig:
    # input
    input_dir: Path

    # output
    output_dir: Path
    checkpoint_db: Path
    tables: OutputTables
    schemas: CsvSchemas

    # runtime
    stop_after: int | None = None          # for testing
    fail_fast: bool = False                # stop on first failure