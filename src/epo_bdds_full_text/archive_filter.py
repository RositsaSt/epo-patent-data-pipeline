from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable, Optional, TypeAlias

import os
import tarfile
import zipfile


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
                # Prefer not to crash; callers doing critical durability may want strict mode.
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
    Read an archive from disk, filter it in memory, write to destination atomically.

    Returns:
      - True if something was kept and written.
      - False if nothing matched (no XMLs kept anywhere).
      
    Raises:
      - Exceptions from parsing/filtering if options.strict is True
      - RuntimeError from validators
      - OSError from file operations

    If cleanup_on_error is True, deletes the .part file on exceptions.
    """
    raw_bytes = source_path.read_bytes()
    filtered_bytes = filter_archive_bytes(raw_bytes, archive_name=source_path.name, rules=rules,options=options)
    if not filtered_bytes:
        return False

    temp_path=None
    try:
        temp_path = write_bytes_atomically(destination_path, filtered_bytes, fsync=True)
        
        # If no validators provided, pick a sensible default for zip outputs
        if validators is None:
            validators = []
            if destination_path.suffix.lower() == ".zip":
                validators.append(validate_zip_crc)
        
        for validator in validators:
            validator(temp_path)
        
        finalize_atomic_write(temp_path, destination_path)
        return True
    
    except Exception:
        if cleanup_on_error and temp_path is not None:
            temp_path.unlink(missing_ok=True) # Delete the temp file if it exists
        raise
