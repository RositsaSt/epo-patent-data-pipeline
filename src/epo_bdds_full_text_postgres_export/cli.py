from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from .config import PostgresExportConfig
from .extract.abstract_extractor import AbstractExtractor
from .extract.description_extractor import DescriptionExtractor
from .extract.claims_extractor import ClaimsExtractor
from .extract.fulltext_extractor import FullTextExtractor
from .io.checkpoint_store import TextFileCheckpointStore
from .io.postgres import PostgresConnectionFactory, PostgresFullTextRepository
from .pipeline.runner import PostgresExportPipeline

# Reuse the existing XML streaming from the graph_export package
from epo_bdds_full_text_graph_export.xml.xml_source import BddsNestedArchiveXmlSource, FileSystemXmlSource
from epo_bdds_full_text_graph_export.xml.xml_stream import XmlStream


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Build CLI parser.
    """
    parser = argparse.ArgumentParser(description="Export EPO BDDS full-text sections to PostgreSQL.")
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--xml-dir", type=Path, help="Directory containing extracted *.xml files",)
    input_group.add_argument("--archives-dir", type=Path, 
                             help="Directory containing BDDS delivery archives (e.g., .zip or .tar.gz) with XMLs.",)

    parser.add_argument("--checkpoint", type=Path, default=Path("data/checkpoints/postgres_fulltext_checkpoint.txt"), 
                        help="Path to checkpoint file storing processed source_ids.",)
    parser.add_argument("--languages", type=str, default=os.getenv("PATENTS_PG_LANGS", "en"),
                                help='Comma-separated language whitelist, e.g. "en,de,fr". Default: en (or PATENTS_PG_LANGS).',)
    parser.add_argument("--commit-every", type=int, default=int(os.getenv("PATENTS_PG_COMMIT_EVERY", "200")),
        help="Commit every N processed XMLs (default: 200 or PATENTS_PG_COMMIT_EVERY).",
    )

    return parser

def main() -> int:
    """
    CLI entrypoint.

    Workflow:
      1) load .env
      2) read DSN + cli args
      3) wire dependencies
      4) stream XMLs
      5) run pipeline
    """
    load_dotenv()
    
    args = build_arg_parser().parse_args()
    
    postgres_dsn = os.getenv("Patents_PG_DSN", "")
    config = PostgresExportConfig(
        postgres_dsn=postgres_dsn, 
        language_whitelist=tuple([x.strip() for x in args.languages.split(",") if x.strip()]), 
        commit_every=args.commit_every,)

    #Wiring
    extractor = FullTextExtractor(
        abstract_extractor=AbstractExtractor(),
        description_extractor=DescriptionExtractor(),
        claims_extractor=ClaimsExtractor(),
    )

    repository = PostgresFullTextRepository(PostgresConnectionFactory(dsn=config.postgres_dsn))
    checkpoint_store = TextFileCheckpointStore(checkpoint_path=args.checkpoint)

    pipeline = PostgresExportPipeline(
        config=config,
        extractor=extractor,
        repository=repository,
        checkpoint_store=checkpoint_store,
    )
    
    # Input selection
    if args.xml_dir is not None:
        xml_source = FileSystemXmlSource(xml_dir=args.xml_dir)
    else:
        xml_source = BddsNestedArchiveXmlSource(top_archives_dir=args.archives_dir)
        
    xml_items = XmlStream(xml_source).iter_xml_items()

    pipeline.run(xml_items)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())