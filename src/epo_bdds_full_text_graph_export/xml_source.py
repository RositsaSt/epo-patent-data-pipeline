from __future__ import annotations

"""
XML source implementation for EPO full‑text archives.

This module discovers XML documents inside nested zip/tar archives
and yields them as (source_id, xml_bytes) pairs.
"""

from io import BytesIO
from pathlib import Path
from typing import Iterator, Optional, Tuple
import tarfile
import zipfile


class NestedArchiveXmlSource:
    """
    Iterate over XML documents stored inside nested zip/tar archives.

    Single responsibility:
        - Discover and stream XML documents from the EPO full‑text layout,
          without knowing anything about their content.
    """

    def __init__(self, final_directory: Path) -> None:
        """
        Args:
            final_directory: Directory containing outer EPO archives (zip/tar).
        """
        self._final_directory = final_directory

    def iter_xml_documents(self) -> Iterator[Tuple[str, bytes]]:
        """
        Yield (document_source_id, xml_bytes) for every XML found.
        """
        if not self._final_directory.exists():
            raise FileNotFoundError(f"XML root does not exist: {self._final_directory}")

        outer_archives = [
            path
            for path in self._final_directory.iterdir()
            if path.is_file() and self._is_archive(path.name)
        ]

        for outer_archive_path in outer_archives:
            yield from self._iter_xml_from_outer_archive(outer_archive_path)

    # ---- outer archive handling ------------------------------------------

    def _iter_xml_from_outer_archive(self, outer_archive_path: Path) -> Iterator[Tuple[str, bytes]]:
        """Yield XML bytes from a single outer archive."""
        archive_kind = self._detect_archive_kind(outer_archive_path.name)
        if archive_kind is None:
            return

        with outer_archive_path.open("rb") as f:
            archive_bytes = f.read()

        if archive_kind == "zip":
            yield from self._iter_xml_from_outer_zip(outer_archive_path, archive_bytes)
        elif archive_kind == "tar":
            yield from self._iter_xml_from_outer_tar(outer_archive_path, archive_bytes)

    def _iter_xml_from_outer_zip(
        self,
        outer_archive_path: Path,
        archive_bytes: bytes,
    ) -> Iterator[Tuple[str, bytes]]:
        """Yield XML bytes from a zip outer archive."""
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as zip_file:
            for member_info in zip_file.infolist():
                if member_info.is_dir():
                    continue

                normalised_name = member_info.filename.replace("\\", "/")
                if not (normalised_name.startswith("DOC/") or normalised_name.startswith("./DOC/")):
                    continue

                if not self._is_archive(member_info.filename):
                    continue

                nested_archive_bytes = zip_file.read(member_info)

                yield from self._iter_xml_from_nested_archive(
                    nested_archive_bytes,
                    member_info.filename,
                    outer_archive_path,
                )

    def _iter_xml_from_outer_tar(
        self,
        outer_archive_path: Path,
        archive_bytes: bytes,
    ) -> Iterator[Tuple[str, bytes]]:
        """Yield XML bytes from a tar/tar.gz outer archive."""
        mode = self._tar_read_mode(outer_archive_path.name)
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode=mode) as tar_file:
            for member in tar_file.getmembers():
                if not member.isfile():
                    continue

                normalised_name = member.name.replace("\\", "/")
                if not (normalised_name.startswith("DOC/") or normalised_name.startswith("./DOC/")):
                    continue

                if not self._is_archive(member.name):
                    continue

                extracted = tar_file.extractfile(member)
                if extracted is None:
                    continue
                nested_archive_bytes = extracted.read()

                yield from self._iter_xml_from_nested_archive(
                    nested_archive_bytes,
                    member.name,
                    outer_archive_path,
                )

    # ---- nested archive handling -----------------------------------------

    def _iter_xml_from_nested_archive(
        self,
        nested_archive_bytes: bytes,
        nested_archive_name: str,
        outer_archive_path: Path,
    ) -> Iterator[Tuple[str, bytes]]:
        """
        Yield XML bytes from a nested archive (zip or tar) inside an outer archive.
        """
        nested_kind = self._detect_archive_kind(nested_archive_name)
        if nested_kind is None:
            return

        if nested_kind == "zip":
            with zipfile.ZipFile(BytesIO(nested_archive_bytes), "r") as nested_zip:
                for member_info in nested_zip.infolist():
                    if member_info.is_dir():
                        continue
                    if not member_info.filename.lower().endswith(".xml"):
                        continue
                    xml_bytes = nested_zip.read(member_info)
                    source_id = (
                        f"{outer_archive_path.name}"
                        f"::{nested_archive_name}"
                        f"::{member_info.filename}"
                    )
                    yield source_id, xml_bytes

        elif nested_kind == "tar":
            mode = self._tar_read_mode(nested_archive_name)
            with tarfile.open(fileobj=BytesIO(nested_archive_bytes), mode=mode) as nested_tar:
                for member in nested_tar.getmembers():
                    if not member.isfile():
                        continue
                    if not member.name.lower().endswith(".xml"):
                        continue
                    extracted = nested_tar.extractfile(member)
                    if extracted is None:
                        continue
                    xml_bytes = extracted.read()
                    source_id = (
                        f"{outer_archive_path.name}"
                        f"::{nested_archive_name}"
                        f"::{member.name}"
                    )
                    yield source_id, xml_bytes

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _is_archive(file_name: str) -> bool:
        """Return True if the file name looks like a supported archive."""
        lower = file_name.lower()
        return (
            lower.endswith(".zip")
            or lower.endswith(".tar")
            or lower.endswith(".tar.gz")
            or lower.endswith(".tgz")
        )

    @staticmethod
    def _detect_archive_kind(file_name: str) -> Optional[str]:
        """Return 'zip' or 'tar' depending on the archive type, or None."""
        lower = file_name.lower()
        if lower.endswith(".zip"):
            return "zip"
        if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return "tar"
        return None

    @staticmethod
    def _tar_read_mode(file_name: str) -> str:
        """Return the appropriate read mode for tarfile.open."""
        lower = file_name.lower()
        if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return "r:gz"
        return "r:"

