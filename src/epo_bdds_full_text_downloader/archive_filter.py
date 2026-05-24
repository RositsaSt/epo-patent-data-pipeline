from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional, TypeAlias

import logging
import os
import shutil
import tarfile
import tempfile
import zipfile

logger = logging.getLogger(__name__)


# =============================================================================
# TYPES
# =============================================================================

Validator: TypeAlias = Callable[[Path], None]


# =============================================================================
# CONFIG
# =============================================================================

@dataclass(frozen=True)
class ArchiveFilterRules:
    """
    Rules for which files to keep during archive filtering.

    - The `basename` prefix is set to "ep" by default to match the naming pattern of EPO XML files, but can be adjusted as needed.
    - If `xml_basename_prefix` is empty, keep all XML files.
    - Otherwise, keep only XML files whose `basename` starts with the prefix.
    """
    xml_basename_prefix: str = "ep"  # Keep empty if all XMLs should be kept
    xml_extension: str = ".xml"


@dataclass(frozen=True)
class ArchiveFilterOptions:
    """
    Behavior knobs for filtering.

    - strict: if True, raise on unexpected archive parsing errors.
              if False, treat unexpected errors as "nothing kept" (returns b"").
    """
    strict: bool = True


# =============================================================================
# ARCHIVE TYPE HELPERS
# =============================================================================

def is_supported_archive(filename: str) -> bool:
    """Return True if filename looks like a supported archive type (zip/tar/tar.gz/tgz)."""
    lower = filename.lower()
    return (
        lower.endswith(".zip")
        or lower.endswith(".tar")
        or lower.endswith(".tar.gz")
        or lower.endswith(".tgz")
    )

def detect_archive_kind(filename: str) -> Optional[str]:
    """
    Return 'zip' or 'tar' for supported archive names, otherwise None.
    """
    lower = filename.lower()
    if lower.endswith(".zip"):
        return "zip"
    if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "tar"
    return None

def tar_open_modes(archive_name: str) -> tuple[str, str]:
    """
    Return (read_mode, write_mode) for tarfile based on extension.
    """
    lower = archive_name.lower()
    if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        return "r:gz", "w:gz"
    return "r:", "w:"


# =============================================================================
# SELECTION POLICY
# =============================================================================

def should_keep_xml(member_path: str, rules: ArchiveFilterRules) -> bool:
    """
    Decide whether an archive member path should be kept as an XML file.
    Uses the `basename` for prefix matching.
    """
    basename = Path(member_path).name.lower()
    if not basename.endswith(rules.xml_extension.lower()):
        return False

    prefix = rules.xml_basename_prefix.lower()
    return True if not prefix else basename.startswith(prefix)


# =============================================================================
# IN-MEMORY FILTERING (RECURSIVE)
# =============================================================================

def filter_archive_bytes(
    archive_bytes: bytes,
    archive_name: str,
    rules: ArchiveFilterRules,
    *,
    options: ArchiveFilterOptions = ArchiveFilterOptions(),
) -> bytes:
    """
    Filter an archive contained in `archive_bytes`.

    - Keeps XML files according to `rules`.
    - Recurses into nested archives (zip/tar/tar.gz/tgz).
    - Returns filtered archive bytes.
    - Returns b"" if nothing matched (no XMLs kept anywhere).
    - If options.strict is False: unexpected parse errors return b"" instead of raising.
    """
    kind = detect_archive_kind(archive_name)
    if kind is None:
        return b""

    try:
        if kind == "zip":
            return _filter_zip_bytes(archive_bytes, rules, options=options)
        if kind == "tar":
            return _filter_tar_bytes(archive_bytes, archive_name, rules, options=options)
    except Exception:
        if options.strict:
            raise
        return b""


def _filter_zip_bytes(
    zip_bytes: bytes,
    rules: ArchiveFilterRules,
    *,
    options: ArchiveFilterOptions,
) -> bytes:
    """
    Filter a ZIP represented as bytes; return filtered ZIP bytes or b"" if nothing kept.
    """
    out_buffer = BytesIO()
    wrote_anything = False

    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zipin:
        with zipfile.ZipFile(out_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zipout:
            for entry in zipin.infolist():
                if entry.is_dir():
                    continue

                member_name = entry.filename

                # Keep XMLs
                if should_keep_xml(member_name, rules):
                    with zipin.open(entry) as f:
                        zipout.writestr(entry, f.read())
                    wrote_anything = True
                    continue

                # Recurse into nested archives
                if is_supported_archive(member_name):
                    with zipin.open(entry) as f:
                        nested_bytes = f.read()

                    filtered_nested = filter_archive_bytes(nested_bytes, archive_name=member_name, rules=rules, options=options)
                    if filtered_nested:
                        #Use member_name as the name in the zipto preserve original path/name inside the archive
                        zipout.writestr(member_name, filtered_nested)
                        wrote_anything = True

    if not wrote_anything:
        return b""

    # Rewind before reading out the bytes
    out_buffer.seek(0)
    return out_buffer.read()


def _filter_tar_bytes(
    tar_bytes: bytes,
    tar_name: str,
    rules: ArchiveFilterRules,
    *,
    options: ArchiveFilterOptions,
) -> bytes:
    """
    Filter a TAR/TAR.GZ/TGZ represented as bytes; return filtered TAR bytes or b"".
    """
    read_mode, write_mode = tar_open_modes(tar_name)

    in_buffer = BytesIO(tar_bytes)
    out_buffer = BytesIO()
    wrote_anything = False

    with tarfile.open(fileobj=in_buffer, mode=read_mode) as tarin:
        with tarfile.open(fileobj=out_buffer, mode=write_mode) as tarout:
            for member in tarin.getmembers():
                if not member.isfile():
                    continue

                member_name = member.name

                # Keep XMLs
                if should_keep_xml(member_name, rules):
                    extracted = tarin.extractfile(member)
                    if extracted is None:
                        continue
                    data = extracted.read()
                    member.size = len(data)
                    tarout.addfile(member, BytesIO(data))
                    wrote_anything = True
                    continue

                # Recurse into nested archives
                if is_supported_archive(member_name):
                    extracted = tarin.extractfile(member)
                    if extracted is None:
                        continue
                    nested_bytes = extracted.read()

                    filtered_nested = filter_archive_bytes(nested_bytes, archive_name=member_name, rules=rules, options=options)
                    if filtered_nested:
                        member.size = len(filtered_nested)
                        tarout.addfile(member, BytesIO(filtered_nested))
                        wrote_anything = True

    if not wrote_anything:
        return b""

    out_buffer.seek(0)
    return out_buffer.read()


# =============================================================================
# DISK-BACKED ZIP FILTERING FOR LARGE BDDS ARCHIVES
# =============================================================================

STREAM_COPY_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB


def _copy_stream(source, destination) -> None:
    """Copy file content incrementally without loading the whole member into RAM."""
    shutil.copyfileobj(source, destination, length=STREAM_COPY_CHUNK_SIZE)


def _new_zip_info(
    entry: zipfile.ZipInfo,
    *,
    compression: int,
) -> zipfile.ZipInfo:
    """
    Create output metadata for a copied ZIP member.

    Direct XML members are compressed; already-compressed nested ZIP members
    are stored without trying to compress them again.
    """
    output_entry = zipfile.ZipInfo(
        filename=entry.filename,
        date_time=entry.date_time,
    )
    output_entry.compress_type = compression
    output_entry.external_attr = entry.external_attr
    output_entry.comment = entry.comment
    output_entry.create_system = entry.create_system
    return output_entry


def _filter_zip_path_to_path(
    source_path: Path,
    destination_path: Path,
    rules: ArchiveFilterRules,
    *,
    options: ArchiveFilterOptions,
    depth: int = 0,
) -> bool:
    """
    Filter a ZIP file from disk to disk using bounded memory.

    The nested ZIP structure is preserved in the filtered outer ZIP.
    """
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    wrote_anything = False
    nested_seen = 0
    nested_kept = 0

    with tempfile.TemporaryDirectory(
        prefix="epo_archive_filter_",
        dir=destination_path.parent,
    ) as temp_directory:
        temporary_dir = Path(temp_directory)

        with zipfile.ZipFile(source_path, "r") as zipin:
            with zipfile.ZipFile(
                destination_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                allowZip64=True,
            ) as zipout:
                for index, entry in enumerate(zipin.infolist(), start=1):
                    if entry.is_dir():
                        continue

                    member_name = entry.filename

                    # Keep XML documents directly inside the current ZIP.
                    if should_keep_xml(member_name, rules):
                        output_entry = _new_zip_info(
                            entry,
                            compression=zipfile.ZIP_DEFLATED,
                        )

                        with zipin.open(entry, "r") as source:
                            with zipout.open(
                                output_entry,
                                "w",
                                force_zip64=True,
                            ) as destination:
                                _copy_stream(source, destination)

                        wrote_anything = True
                        continue

                    # Recurse only into nested ZIP files.
                    if not member_name.lower().endswith(".zip"):
                        continue

                    nested_seen += 1

                    # An empty nested ZIP cannot contain XML and should not
                    # cause the complete delivery to fail.
                    if entry.file_size == 0:
                        logger.warning("Skipping empty nested ZIP: %s", member_name)
                        continue

                    nested_source = temporary_dir / f"source_{index}.zip"
                    nested_filtered = temporary_dir / f"filtered_{index}.zip"

                    with zipin.open(entry, "r") as source:
                        with nested_source.open("wb") as destination:
                            _copy_stream(source, destination)

                    try:
                        nested_has_matches = _filter_zip_path_to_path(
                            source_path=nested_source,
                            destination_path=nested_filtered,
                            rules=rules,
                            options=options,
                            depth=depth + 1,
                        )
                    except zipfile.BadZipFile:
                        if options.strict:
                            raise

                        logger.warning(
                            "Skipping invalid nested ZIP: %s",
                            member_name,
                        )
                        nested_has_matches = False

                    if nested_has_matches:
                        # A nested ZIP is already compressed. Store it in the
                        # outer ZIP without wasting time recompressing it.
                        output_entry = _new_zip_info(
                            entry,
                            compression=zipfile.ZIP_STORED,
                        )

                        with nested_filtered.open("rb") as source:
                            with zipout.open(
                                output_entry,
                                "w",
                                force_zip64=True,
                            ) as destination:
                                _copy_stream(source, destination)

                        nested_kept += 1
                        wrote_anything = True

                    nested_source.unlink(missing_ok=True)
                    nested_filtered.unlink(missing_ok=True)

                    if depth == 0 and nested_seen % 500 == 0:
                        logger.info(
                            "Processed %d nested ZIPs; %d contained matching XML files.",
                            nested_seen,
                            nested_kept,
                        )

    if not wrote_anything:
        destination_path.unlink(missing_ok=True)
        return False

    if depth == 0:
        logger.info(
            "Finished filtering outer ZIP: %d nested ZIPs processed; "
            "%d retained.",
            nested_seen,
            nested_kept,
        )

    return True


# =============================================================================
# OUTPUT VALIDATION
# =============================================================================

def validate_zip_crc(path: Path) -> None:
    """
    Raise RuntimeError if `path` is not a valid ZIP or fails CRC integrity checks.
    """
    if not zipfile.is_zipfile(path):
        raise RuntimeError("Invalid ZIP (missing central directory or not a ZIP)")

    with zipfile.ZipFile(path) as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise RuntimeError(f"Invalid ZIP (CRC error in file {bad_member})")


# =============================================================================
# DISK I/O (ATOMIC WRITE)
# =============================================================================

def write_bytes_atomically(
    destination: Path,
    data: bytes,
    *,
    fsync: bool = True,
) -> Path:
    """
    Write `data` to `destination` atomically using a sibling .part file.

    Returns the temporary path written (destination.suffix + '.part').

    NOTE: This function does not rename to final. Caller can validate first.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    temp_path = destination.with_suffix(destination.suffix + ".part")
    temp_path.unlink(missing_ok=True)

    with temp_path.open("wb") as f:
        f.write(data)
        f.flush()
        if fsync:
            try:
                os.fsync(f.fileno())
            except OSError:
                # Some mounts/filesystems do not support fsync reliably.
                # Continue without crashing.
                pass

    return temp_path


def finalize_atomic_write(temp_path: Path, destination: Path) -> None:
    """Replace destination with temp_path (atomic on same filesystem)."""
    temp_path.replace(destination)


# =============================================================================
# HIGH-LEVEL API
# =============================================================================

def filter_archive_file(
    source_path: Path,
    destination_path: Path,
    rules: ArchiveFilterRules,
    *,
    options: ArchiveFilterOptions = ArchiveFilterOptions(),
    validators: Optional[list[Validator]] = None,
    cleanup_on_error: bool = True,
) -> bool:
    """
    Filter an archive to `destination_path`.

    ZIP deliveries use disk-backed bounded-memory processing suitable for
    multi-gigabyte BDDS archives. The existing in-memory path is retained for
    non-ZIP formats until disk-backed TAR processing is implemented.
    """
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = destination_path.with_suffix(destination_path.suffix + ".part")
    temp_path.unlink(missing_ok=True)

    try:
        if source_path.name.lower().endswith(".zip"):
            kept_any = _filter_zip_path_to_path(
                source_path=source_path,
                destination_path=temp_path,
                rules=rules,
                options=options,
            )
        else:
            logger.warning(
                "Using in-memory filtering for non-ZIP archive: %s",
                source_path.name,
            )
            raw_bytes = source_path.read_bytes()
            filtered_bytes = filter_archive_bytes(
                raw_bytes,
                archive_name=source_path.name,
                rules=rules,
                options=options,
            )

            if not filtered_bytes:
                return False

            with temp_path.open("wb") as output_file:
                output_file.write(filtered_bytes)

            kept_any = True

        if not kept_any:
            temp_path.unlink(missing_ok=True)
            return False

        validators_to_run = list(validators or [])

        if validators is None and destination_path.suffix.lower() == ".zip":
            validators_to_run.append(validate_zip_crc)

        for validator in validators_to_run:
            validator(temp_path)

        finalize_atomic_write(temp_path, destination_path)

        logger.info(
            "Filtered archive written successfully: %s",
            destination_path,
        )

        return True

    except Exception:
        if cleanup_on_error:
            temp_path.unlink(missing_ok=True)
        raise
