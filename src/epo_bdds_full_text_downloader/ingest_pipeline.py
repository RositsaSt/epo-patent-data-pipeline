from __future__ import annotations

from dataclasses import dataclass,field
from pathlib import Path
from typing import Mapping, Optional, Protocol, Sequence
import logging
import shutil

import requests

import downloader
import archive_filter
from manifest import CsvManifest, ManifestStatus

logger = logging.getLogger(__name__)


# =============================================================================
# PROTOCOLS (DEPENDENCY INGESTION)
# =============================================================================

class ArtifactValidator(Protocol):
    """Callable that validates an on-disk artifact. Should raise on failure."""
    def __call__(self, path: Path) -> None: ...


class MoveFunction(Protocol):
    """Callable that moves a file from source directory to destination directory."""
    def __call__(self, source_dir: Path, destination_dir: Path) -> None: ...


def move_across_filesystems(source_dir: Path, destination_dir: Path) -> None:
    """Move `source_dir` to `destination_dir` safely across filesystems."""
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_dir), str(destination_dir))


# =============================================================================
# CONFIG
# =============================================================================

@dataclass(frozen=True)
class StorageLayout:
    """Directory layout for the ingest pipeline."""
    raw_download_dir: Path      # raw downloads (.zip/.tar/.tgz)
    filtered_staging_dir: Path  # filtered outputs (same filename as raw)
    final_dir: Path             # long-term storage


@dataclass(frozen=True)
class DownloadSettings:
    """Settings controlling download behavior."""
    headers: Mapping[str, str] = field(default_factory=lambda: dict(downloader.DEFAULT_HEADERS))
    chunk_size: int = downloader.CHUNK_SIZE
    connect_read_timeout: tuple[float, float] = (30.0, 300.0)


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for a full ingest run."""
    product_id: int
    storage: StorageLayout

    filter_rules: archive_filter.ArchiveFilterRules
    filter_options: archive_filter.ArchiveFilterOptions = archive_filter.ArchiveFilterOptions(strict=True)

    manifest: CsvManifest = field(default_factory=lambda: CsvManifest(Path("manifest.csv")))
    download: DownloadSettings = field(default_factory=DownloadSettings)

    # Validators are stage-specific.
    raw_validators: Sequence[ArtifactValidator] = (downloader.validate_zip_crc,)
    filtered_validators: Sequence[ArtifactValidator] = (archive_filter.validate_zip_crc,)

    mover: MoveFunction = move_across_filesystems


# =============================================================================
# PIPELINE
# =============================================================================

@dataclass(frozen=True)
class ArtifactPaths:
    """Concrete locations for one artifact across pipeline stages."""
    filename: str
    raw_path: Path
    filtered_path: Path
    final_path: Path

class IngestPipeline:
    """Coordinate download -> filter -> move for one BDDS archive file."""

    def __init__(self, config: PipelineConfig, *, session: Optional[requests.Session] = None) -> None:
        self._cfg = config
        self._session = session or requests.Session()

    @property
    def session(self) -> requests.Session:
        return self._session

    def ingest_file(self, *,delivery_id: str, file_id: str, filename: str) -> None:
        """
        Ingest a single BDDS archive file from a delivery.

        Updates manifest at each major stage to allow safe resume.
        Never deletes the raw download before the final artifact is successfully moved.
        """
        if not archive_filter.is_supported_archive(filename):
            self._mark(filename, ManifestStatus.SKIPPED, message="unsupported archive type")
            logger.info(f"Skipped unsupported archive: {filename}")
            return

        paths = self._build_paths(filename)

        # Ensure raw download exists and is valid (may reuse a valid leftover from a prior run).
        if self._final_is_good(paths.final_path):
            self._mark(
                filename,
                ManifestStatus.MOVED,
                final_size=str(paths.final_path.stat().st_size),
                message="Final exists and is valid",
            )
            logger.info("Final already exists and is valid: %s", filename)

            # Remove temporary raw/staging leftovers from an interrupted prior run.
            self._cleanup_after_success(paths)
            return

        # If staging exists and validates, just move to final.
        if self._filtered_is_good(paths.filtered_path):
            if self._move_filtered_to_final(paths):
                self._cleanup_after_success(paths)
            return

        # Ensure the raw download is complete.
        if not self._ensure_raw_download(paths, delivery_id=delivery_id,file_id=file_id):
            return

        # Filter the raw download to staging.
        if not self._filter_raw_to_staging(paths):
            return

        # Move from staging to final.
        if not self._move_filtered_to_final(paths):
            return

        #Cleanup(delete) raw download after successful move.
        self._cleanup_after_success(paths)


    # =============================================================================
    # STAGE HELPERS
    # =============================================================================

    def _build_paths(self, filename: str) -> ArtifactPaths:
        storage = self._cfg.storage
        return ArtifactPaths(
            filename=filename,
            raw_path=storage.raw_download_dir / filename,
            filtered_path=storage.filtered_staging_dir / filename,
            final_path=storage.final_dir / filename,
        )

    def _ensure_raw_download(
        self,
        paths: ArtifactPaths,
        *,
        delivery_id: str,
        file_id: str,
    ) -> bool:
        """
        Ensure the temporary raw archive exists and is valid.

        Raw archives are retained only until the filtered final artifact is
        successfully produced. A valid leftover raw ZIP may be reused after an
        interrupted or failed prior run.
        """
        url = self._build_download_url(delivery_id=delivery_id, file_id=file_id)
        self._cfg.storage.raw_download_dir.mkdir(parents=True, exist_ok=True)

        # Recovery path only: reuse a valid temporary raw ZIP left from an
        # interrupted or failed previous run.
        if self._artifact_is_good(paths.raw_path, stage="raw"):
            self._mark(
                paths.filename,
                ManifestStatus.DOWNLOADED,
                raw_size=str(paths.raw_path.stat().st_size),
                message="Valid temporary raw archive reused",
            )
            logger.info("Reusing valid temporary raw archive: %s", paths.raw_path)
            return True

        # Remove an invalid raw ZIP or an unfinished .part download.
        self._delete_partials(paths.raw_path)

        logger.info(
            "Downloading temporary raw archive %s; "
            "size will be obtained from the streamed GET response.",
            paths.filename,
        )

        try:
            downloader.download_stream(
                session=self.session,
                url=url,
                destination=paths.raw_path,
                headers=self._cfg.download.headers,
                chunk_size=self._cfg.download.chunk_size,
                expected_size=None,
                validators=self._validators_for_path(paths.raw_path, stage="raw"),
                timeout=self._cfg.download.connect_read_timeout,
            )
        except Exception as exc:
            self._mark(
                paths.filename,
                ManifestStatus.FAILED,
                message=f"Download failed: {exc}",
            )
            logger.error("Download failed for %s: %s", paths.filename, exc)
            return False

        self._mark(
            paths.filename,
            ManifestStatus.DOWNLOADED,
            raw_size=str(paths.raw_path.stat().st_size),
            message="Temporary raw download successful",
        )
        return True

    def _filter_raw_to_staging(self, paths: ArtifactPaths) -> bool:
        """Filter the raw archive to keep only desired XML files, writing to staging."""
        self._cfg.storage.filtered_staging_dir.mkdir(parents=True, exist_ok=True)
        self._delete_partials(paths.filtered_path)

        logger.info(f"Filtering {paths.filename} to staging")
        try:
            kept_any = archive_filter.filter_archive_file(
                source_path=paths.raw_path,
                destination_path=paths.filtered_path,
                rules=self._cfg.filter_rules,
                options=self._cfg.filter_options,
                validators=list(self._validators_for_path(paths.filtered_path, stage="filtered")),
                cleanup_on_error=True,
            )

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc!r}"

            self._mark(
                paths.filename,
                ManifestStatus.FAILED,
                raw_size=str(paths.raw_path.stat().st_size),
                message=f"Filtering failed: {error_message}",
            )

            logger.exception(
                "Filtering failed for %s: %s",
                paths.filename,
                error_message,
            )
            return False

        if not kept_any:
            self._mark(paths.filename, ManifestStatus.EMPTY, raw_size=str(paths.raw_path.stat().st_size), message="No matching XML files found",)
            logger.warning(f"No matching XML files found in {paths.filename}")
            return False

        self._mark(paths.filename, ManifestStatus.CLEANED,
                   raw_size=str(paths.raw_path.stat().st_size),
                   filtered_size=str(paths.filtered_path.stat().st_size),
                   message="Filtering successful",)
        return True

    def _move_filtered_to_final(self, paths: ArtifactPaths) -> bool:
        """Move the filtered artifact from staging to final storage."""
        # If final exists but invalid, remove it before moving.
        if paths.final_path.exists() and not self._final_is_good(paths.final_path):
            logger
            paths.final_path.unlink(missing_ok=True)

        # If staging exists but invalid, remove it and force re-filter.
        if paths.filtered_path.exists() and not self._filtered_is_good(paths.filtered_path):
            logger.warning(f"Staging artifact exists but is invalid, deleting: {paths.filtered_path}")
            self._delete_partials(paths.filtered_path)
            return False

        if not paths.filtered_path.exists():
            logger.error(f"Filtered artifact does not exist for moving to final: {paths.filtered_path}")
            return False

        try:
            self._cfg.mover(paths.filtered_path, paths.final_path)

        except Exception as exc:
            self._mark(paths.filename, ManifestStatus.FAILED,
                       raw_size=str(paths.raw_path.stat().st_size) if paths.raw_path.exists() else "",
                       filtered_size=str(paths.filtered_path.stat().st_size) if paths.filtered_path.exists() else "",
                       message=f"Move to final failed: {exc}",)
            logger.error(f"Move to final failed for {paths.filename}: {exc}")
            return False

        self._mark(paths.filename, ManifestStatus.MOVED,
                   final_size=str(paths.final_path.stat().st_size),
                   message="Moved to final successfully",)
        logger.info(f"Moved {paths.filename} to final storage")
        return True

    def _cleanup_after_success(self, paths: ArtifactPaths) -> None:
        """Delete the raw download after successful move to final."""
        # Delete raw + parts after successful move to final.
        self._delete_partials(paths.raw_path)
        self._delete_partials(paths.filtered_path)

        # Best-effort cleanup of empty directories.
        self._rmdir_if_empty(self._cfg.storage.raw_download_dir)
        self._rmdir_if_empty(self._cfg.storage.filtered_staging_dir)


    # =============================================================================
    # Validation / Manifest / Utilities
    # =============================================================================

    def _validators_for_path(self, path: Path, *, stage: str) -> Sequence[ArtifactValidator]:
        """Return the appropriate validators for a given path and pipeline stage."""
        suffix = path.suffix.lower()
        if suffix == ".zip":
            if stage == "raw":
                return self._cfg.raw_validators
            if stage in {"filtered", "final"}:
                return self._cfg.filtered_validators
        # For non-zip files or stages without specific validators, return empty.
        return ()

    def _filtered_is_good(self, filtered_path: Path) -> bool:
        """Check if the filtered artifact exists and validates."""
        return self._artifact_is_good(filtered_path, stage="filtered")

    def _final_is_good(self, final_path: Path) -> bool:
        """Return True if the final artifact exists and appears valid."""
        return self._artifact_is_good(final_path, stage="final")

    def _artifact_is_good(self, path: Path, *, stage: str) -> bool:
        """Check if an artifact at a given path exists and passes validation."""
        if not path.exists():
            return False

        validators = self._validators_for_path(path, stage=stage)
        for validate in validators:
            try:
                validate(path)
            except Exception:
                return False
        return True

    def _build_download_url(self, *, delivery_id: str, file_id: str) -> str:
        """Construct the download URL for a given delivery and file ID."""
        base = downloader.BASE_URL
        return f"{base}/products/{self._cfg.product_id}/delivery/{delivery_id}/file/{file_id}/download"

    def _mark(self, filename: str, status: ManifestStatus, **fields: str) -> None:
        """Helper to update the manifest for a given filename and status."""
        self._cfg.manifest.mark(filename, status, **fields)

    @staticmethod
    def _delete_partials(path: Path) -> None:
        """Delete a file and its .part counterpart if they exist."""
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".part").unlink(missing_ok=True)

    @staticmethod
    def _rmdir_if_empty(dir_path: Path) -> None:
        """Remove a directory if it is empty."""
        try:
            dir_path.rmdir()
        except OSError:
            pass
