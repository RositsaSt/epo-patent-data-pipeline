from __future__ import annotations

import argparse
from pathlib import Path

from .config import ExportConfig
from .io.paths import build_default_config
from .pipeline.runner import build_pipeline
from .xml.xml_source import FileSystemXmlSource
from .xml.xml_stream import XmlStream


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("epo-bdds-full-text-graph-export")
    p.add_argument("--input", required=True, type=Path, help="Directory containing XML files (or extracted XMLs).")
    p.add_argument("--out", required=True, type=Path, help="Output directory for CSV tables and checkpoint DB.")
    p.add_argument("--stop-after", type=int, default=None, help="Process only N XMLs then exit.")
    p.add_argument("--fail-fast", action="store_true", help="Stop at first parse error.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    config = build_default_config(
        input_dir=args.input,
        output_dir=args.out,
        stop_after=args.stop_after,
        fail_fast=args.fail_fast,
    )

    xml_source = FileSystemXmlSource(root_dir=config.input_dir)
    xml_items = XmlStream(xml_source).iter_xml_items()

    pipeline = build_pipeline(config)
    pipeline.run(xml_items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())