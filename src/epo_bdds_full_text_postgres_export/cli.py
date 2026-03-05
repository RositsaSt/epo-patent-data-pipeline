from __future__ import annotations

import argparse
from pathlib import Path

from .config import PostgresExportConfig
from .extract.abstract_extractor import AbstractExtractor
from .extract.description_extractor import DescriptionExtractor
from .extract.claims_extractor import ClaimsExtractor
from .extract.fulltext_extractor import FullTextExtractor
from .io.postgres import PostgresFullTextRepository
from .pipeline.runner import PostgresExportPipeline, ProcessedXmlCheckpointStore

# Reuse the existing XML streaming
from epo_bdds_full_text_graph_export.xml.xml_source import BddsNestedArchiveXmlSource, FileSystemXmlSource
from epo_bdds_full_text_graph_export.xml.xml_stream import XmlStream


def main() -> int:
    ap = argparse.ArgumentParser()
    
    input_group = ap.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--xml-dir", type=Path, help="Directory containing extracted *.xml files",)
    input_group.add_argument("--archives-dir", type=Path, help="Directory containing BDDS delivery archives (e.g., .zip or .tar.gz) with XMLs.")

    ap.add_argument("--checkpoint", type=Path, default=Path("data/checkpoints/postgres_fulltext_checkpoint.txt"))
    args = ap.parse_args()

    cfg = PostgresExportConfig()
    cfg.validate()

    extractor = FullTextExtractor(
        abstract_extractor=AbstractExtractor(),
        description_extractor=DescriptionExtractor(),
        claims_extractor=ClaimsExtractor(),
    )

    repo = PostgresFullTextRepository(cfg.pg_dsn)
    checkpoint = ProcessedXmlCheckpointStore(str(args.checkpoint))

    pipeline = PostgresExportPipeline(
        config=cfg,
        extractor=extractor,
        repo=repo,
        checkpoint=checkpoint,
    )
    
    if args.xml_dir is not None:
        xml_source = FileSystemXmlSource(xml_dir=args.xml_dir)
    else:
        xml_source = BddsNestedArchiveXmlSource(top_archives_dir=args.archives_dir)
        
    xml_items = XmlStream(xml_source).iter_xml_items()

    pipeline.run(xml_items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())