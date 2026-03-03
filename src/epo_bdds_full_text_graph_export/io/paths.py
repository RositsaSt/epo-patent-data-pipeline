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
        ipc_classifications_csv=output_dir / "nodes_ipc_classification.csv",
        cpc_classifications_csv=output_dir / "nodes_cpc_classification.csv",
        applicants_csv=output_dir / "nodes_applicant.csv",
        inventors_csv=output_dir / "nodes_inventor.csv",
        attorney_representatives_csv=output_dir / "nodes_attorney_representative.csv",
        citations_csv=output_dir / "rels_cites.csv",
        relationships_csv=output_dir / "rels_core.csv",
    )

    # IMPORTANT: Adjust fieldnames with your actual Neo4j import headers.
    schemas = CsvSchemas(
        publications_fields=[ "pub_id", "country", "pub_number", "kind_code", "publication_date", "pub_language", "source_id"],
        applications_fields=["appln_id", "appln_country", "appln_number", "appln_kind_code", "appln_filing_date", 
                             "gazette_date", "gazette_issue", "source_id"],
        ipc_classifications_fields=["ipc_raw_code", "ipc_long_code", "ipc_short_code", "source_id"],
        cpc_classifications_fields=["cpc_raw_code", "cpc_long_code", "cpc_short_code", "source_id"],
        applicants_fields=["applicant_name", "applicant_epo_id", "applicant_reference", "applicant_address", 
                           "applicant_city", "applicant_country", "source_id"],
        inventors_fields=["inventor_name", "inventor_address", "inventor_city", "inventor_country", "source_id"],
        attorney_representatives_fields=["attorney_name", "attorney_sfx", "attorney_epo_id", 
                                         "attorney_address", "attorney_city", "attorney_country", "source_id"],
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