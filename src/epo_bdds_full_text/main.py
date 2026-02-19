from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import requests

import archive_filter
import downloader
from ingest_pipeline import DownloadSettings, IngestPipeline, PipelineConfig, StorageLayout
from manifest import CsvManifest


logger = logging.getLogger("bds_ingest_main")


# =============================================================================
# CLI AND CONFIGURATION
# =============================================================================

def configure_logging(verbosity: int) -> None:
    """
    Configure logging level.

    Args:
        verbosity: 0=WARNING, 1=INFO, 2+=DEBUG
    """
    level = logging.WARNING if verbosity <= 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """
    Parse CLI arguments for the ingest runner.

    Returns:
        Namespace of resolved settings.
    """
    parser = argparse.ArgumentParser(description="BDDS full-text ingest runner")

    parser.add_argument("--product-id", type=int, default=downloader.PRODUCT_ID, help="BDDS product ID (default: 32)")
    parser.add_argument("--base-url", type=str, default=downloader.BASE_URL, help="BDDS API base URL")

    parser.add_argument("--raw-dir", type=Path, default=Path("/tmp/epo_tmp_download"), help="Raw download directory")
    parser.add_argument("--staging-dir", type=Path, default=Path("/tmp/epo_clean_staging"), help="Filtered staging directory")
    parser.add_argument("--final-dir", type=Path, default=Path("/mnt/d/epo_data/epo_fulltext_clean"), help="Final output directory")

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Manifest CSV path (default: <final-dir>/_manifest.csv)",
    )

    parser.add_argument(
        "--xml-prefix",
        type=str,
        default="ep",
        help="Keep XML files whose basename starts with this prefix (empty keeps all XMLs) (default: ep).",
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        help="If set, archive filtering errors are tolerated (strict=False).",
    )

    parser.add_argument("-v", "--verbose", action="count", default=1, help="Verbosity: -v=INFO, -vv=DEBUG")

    return parser.parse_args(argv)


# =============================================================================
# COMPOSITION HELPERS
# =============================================================================

def build_manifest_path(final_output_dir: Path, explicit_manifest_path: Optional[Path]) -> Path:
    """Return the manifest path, defaulting to <final_dir>/_manifest.csv."""
    return explicit_manifest_path if explicit_manifest_path is not None else (final_output_dir / "_manifest.csv")


def build_pipeline_config(args: argparse.Namespace) -> PipelineConfig:
    """
    This is a composition helper that translates raw CLI args into structured config objects.
    """
    final_output_dir: Path = args.final_dir
    manifest_path = build_manifest_path(final_output_dir, args.manifest_path)

    storage_layout = StorageLayout(
        raw_download_dir=args.raw_dir,
        filtered_staging_dir=args.staging_dir,
        final_dir=final_output_dir,
    )

    manifest = CsvManifest(manifest_path)

    filter_rules = archive_filter.ArchiveFilterRules(xml_basename_prefix=args.xml_prefix)
    filter_options = archive_filter.ArchiveFilterOptions(strict=not args.non_strict)

    download_settings = DownloadSettings(
        headers=downloader.DEFAULT_HEADERS,
        chunk_size=downloader.CHUNK_SIZE,
        connect_read_timeout=(30.0, 300.0),
    )

    return PipelineConfig(
        product_id=args.product_id,
        storage=storage_layout,
        filter_rules=filter_rules,
        filter_options=filter_options,
        manifest=manifest,
        download=download_settings,
    )

# =============================================================================
# RUN
# =============================================================================

def build_product_metadata_url(base_url: str, product_id: int) -> str:
    """
    Build the BDDS product metadata URL.

    NOTE: This is not a download URL; it returns the JSON describing deliveries/files.
    """
    return f"{base_url}/products/{product_id}"

def run_ingest(session: requests.Session, pipeline: IngestPipeline, base_url: str, product_id: int) -> None:
    """
    Fetch product metadata and ingest all archives.

    Args:
        session: requests session for HTTP calls
        pipeline: configured pipeline to process each file
        base_url: BDDS API base URL
        product_id: BDDS product ID
    """
    product_metadata_url = build_product_metadata_url(base_url=base_url, product_id=product_id)
    logger.info("Fetching product metadata: %s", product_metadata_url)

    product_metadata = downloader.get_json(session, product_metadata_url)
    
    archive_count = 0
    for delivery_id, file_id, filename, expected_size in downloader.iter_archive_refs(product_metadata):
        archive_count += 1
        pipeline.ingest_file(delivery_id=delivery_id, file_id=file_id, filename=filename)

    logger.info("Found %d archive files in metadata", archive_count)


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    configure_logging(args.verbose)

    pipeline_config = build_pipeline_config(args)

    # Reuse one session across the entire run (connection pooling).
    with requests.Session() as session:
        pipeline = IngestPipeline(pipeline_config, session=session)
        run_ingest(session, pipeline, base_url=args.base_url, product_id=args.product_id)

    logger.info("Done.")


if __name__ == "__main__":
    main()
