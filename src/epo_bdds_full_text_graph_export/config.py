from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class OutputTables:
    """Output CSV file locations for Neo4j import."""
    publications_csv: Path
    applications_csv: Path
    ipc_classifications_csv: Path
    cpc_classifications_csv: Path
    applicants_csv: Path
    inventors_csv: Path
    attorney_representatives_csv: Path
    citations_csv: Path
    relationships_csv: Path
    source_files_csv: Path


@dataclass(frozen=True)
class CsvSchemas:
    """
    CSV headers (fieldnames) for each output table.

    Tip: keep these aligned with Neo4j's LOAD CSV headers you plan to use.
    """
    publications_fields: Sequence[str]
    applications_fields: Sequence[str]
    ipc_classifications_fields: Sequence[str]
    cpc_classifications_fields: Sequence[str]
    applicants_fields: Sequence[str]
    inventors_fields: Sequence[str]
    attorney_representatives_fields: Sequence[str]
    citations_fields: Sequence[str]
    relationships_fields: Sequence[str]
    source_files_fields: Sequence[str]


@dataclass(frozen=True)
class ExportConfig:
    """
    Configuration for a graph export run.

    The pipeline is intentionally decoupled from how XML bytes are obtained;
    an XmlSource is responsible for producing (source_id, xml_bytes).
    """
    # Input/Output
    output_dir: Path
    checkpoint_db: Path
    tables: OutputTables
    schemas: CsvSchemas

    # Runtime controls
    stop_after: int | None = None          # for testing
    fail_fast: bool = False                # stop on first failure