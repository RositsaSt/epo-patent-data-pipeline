from __future__ import annotations

from pathlib import Path

from ..config import CsvSchemas, ExportConfig, OutputTables


def build_default_config(
    *,
    output_dir: Path,
    stop_after: int | None = None,
    fail_fast: bool = False,
) -> ExportConfig:
    """
    Build a default ExportConfig given an output directory.

    Notes:
    - This function defines default filenames and default CSV headers.
    - Adjust the fieldnames to match your Neo4j import conventions.
    """
    output_dir = output_dir.expanduser().resolve()

    tables = OutputTables(
        publications_csv=output_dir / "nodes_publication.csv",
        applications_csv=output_dir / "nodes_application.csv",
        persons_csv=output_dir / "nodes_person.csv",
        citations_csv=output_dir / "rels_cites.csv",
        relationships_csv=output_dir / "rels_core.csv",
    )

    # IMPORTANT: Adjust fieldnames with your actual Neo4j import headers.
    schemas = CsvSchemas(
        publications_fields=["pub_id", "country", "doc_number", "kind", "publication_date", "source_id"],
        applications_fields=["appln_id", "appln_number", "appln_country", "filing_date", "source_id"],
        persons_fields=["person_id", "name", "role", "source_id"],
        citations_fields=["from_pub_id", "to_pub_id", "cite_type", "source_id"],
        relationships_fields=["from_id", "to_id", "rel_type", "source_id"],
    )

    checkpoint_db = output_dir / "checkpoint" / "processed_xml.sqlite"

    return ExportConfig(
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        tables=tables,
        schemas=schemas,
        stop_after=stop_after,
        fail_fast=fail_fast,
    )