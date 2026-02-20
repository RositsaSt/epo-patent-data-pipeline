from __future__ import annotations

"""
Thin CLI wrapper around the `graph_export` package.

This keeps the existing `python graph_export.py` entry point while moving
the production logic into reusable modules under `graph_export/`.
"""

import argparse
import logging
from pathlib import Path
from typing import List, Optional

from .neo4j_csv_writer import Neo4jCsvGraphWriter
from .service import GraphExportService
from .xml_parser import XmlPatentDocumentParser
from .xml_source import NestedArchiveXmlSource


def parse_command_line_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse and validate command‑line arguments for the graph export tool.
    """
    parser = argparse.ArgumentParser(
        description="Export EP full‑text XMLs (inside nested archives) to Neo4j CSVs.",
    )

    parser.add_argument(
        "--xml-root",
        type=Path,
        default=Path("/mnt/d/epo_bdds/epo_full_text/filtered_epo_full_text"),
        help="Root directory (final_dir) containing outer EP archives (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("./graph_export_output"),
        help="Directory where CSV files will be written (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of XML documents to process (for testing).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=1,
        help="Verbosity: -v=INFO, -vv=DEBUG",
    )

    return parser.parse_args(argv)


def configure_logging(verbosity: int) -> None:
    """
    Configure logging according to a simple verbosity scheme.
    """
    level = logging.WARNING if verbosity <= 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point."""
    args = parse_command_line_arguments(argv)
    configure_logging(args.verbose)

    xml_source = NestedArchiveXmlSource(args.xml_root)
    xml_parser = XmlPatentDocumentParser()
    graph_writer = Neo4jCsvGraphWriter(args.out_dir)

    service = GraphExportService(
        xml_source=xml_source,
        xml_parser=xml_parser,
        graph_writer=graph_writer,
        document_limit=args.limit,
    )
    processed = service.run()
    logging.getLogger("graph_export").info("Finished graph export, processed %d documents.", processed)


if __name__ == "__main__":  # pragma: no cover - CLI guard
    main()



