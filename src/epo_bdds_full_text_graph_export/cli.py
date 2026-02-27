from __future__ import annotations

import argparse
from pathlib import Path

from .io.paths import build_default_config
from .pipeline.runner import build_pipeline
from .xml.xml_source import BddsNestedArchiveXmlSource, FileSystemXmlSource
from .xml.xml_stream import XmlStream


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("epo-bdds-full-text-graph-export")
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--xml-dir", type=Path, help="Directory containing extracted *.xml files",)
    input_group.add_argument("--archives-dir", type=Path, help="Directory containing BDDS delivery archives (e.g., .zip or .tar.gz) with XMLs.")
    
    parser.add_argument("--out", required=True, type=Path, help="Output directory for CSV tables and checkpoint DB.")
    parser.add_argument("--stop-after", type=int, default=None, help="Stop after processing this many XML items (for testing).")
    parser.add_argument("--fail-fast", action="store_true", help="Stop immediately on the first error (useful for debugging).")
    
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    config = build_default_config(
        #input_dir=args.input,
        output_dir=args.out,
        stop_after=args.stop_after,
        fail_fast=args.fail_fast,
    )

    if args.xml_dir is not None:
        xml_source = FileSystemXmlSource(xml_dir=args.xml_dir)
    else:
        xml_source = BddsNestedArchiveXmlSource(top_archives_dir=args.archives_dir)
        
    xml_items = XmlStream(xml_source).iter_xml_items()

    pipeline = build_pipeline(config)
    pipeline.run(xml_items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())