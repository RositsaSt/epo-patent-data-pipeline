from __future__ import annotations

import io
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


@dataclass(frozen=True)
class XmlPayload:
    """A single XML document extracted from an archive traversal."""
    source_id: str
    xml_bytes: bytes


def iter_doc_xml_from_top_archive(top_archive_path: Path) -> Iterator[XmlPayload]:
    """
    Recursively yield all *.xml files that exist under DOC/ in a top-level
    archive (zip/tar/tar.gz/tgz).

    Nested archives found under DOC/** are opened recursively.

    source_id is stable and checkpoint-friendly, e.g.:
      TOP.zip::DOC/....../nested.zip::EP123...A1.xml
    """
    archive_kind = _detect_archive_kind_from_name(top_archive_path.name.lower())
    if archive_kind is None:
        raise ValueError(f"Unsupported top archive type: {top_archive_path}")

    chain = top_archive_path.name

    if archive_kind == "zip":
        with zipfile.ZipFile(top_archive_path, "r") as zf:
            yield from _walk_zip(
                zf=zf,
                parent_chain=chain,
                doc_only=True,
            )

    if archive_kind in ("tar", "tar.gz", "tgz"):
        tar_mode = _tar_mode_from_name(top_archive_path.name.lower())
        with tarfile.open(top_archive_path, mode=tar_mode) as tf:
            yield from _walk_tar(
                tf=tf,
                parent_chain=chain,
                doc_only=True,
            )


# ----------------------------
# ZIP walking
# ----------------------------

def _walk_zip(
    *,
    zf: zipfile.ZipFile,
    parent_chain: str,
    doc_only: bool,
) -> Iterator[XmlPayload]:
    # zipfile does not guarantee any order, so we sort by filename for deterministic processing.
    members = sorted(zf.infolist(), key=lambda i: i.filename)

    for info in members:
        if info.is_dir():
            continue

        member_path = info.filename

        # Only consider files under DOC/ if doc_only=True.
        # Once we are inside DOC/, we set doc_only=False for nested archives,
        # because their internal paths may not start with DOC/ anymore.
        if doc_only and not _is_under_doc(member_path):
            continue

        lower = member_path.lower()

        if lower.endswith(".xml"):
            xml_bytes = zf.read(info)
            source_id = f"{parent_chain}::{member_path}"
            yield XmlPayload(source_id=source_id, xml_bytes=xml_bytes)
            continue

        nested_kind = _detect_archive_kind_from_name(lower)
        if nested_kind is None:
            continue

        nested_bytes = zf.read(info)
        nested_chain = f"{parent_chain}::{member_path}"

        if nested_kind == "zip":
            with zipfile.ZipFile(io.BytesIO(nested_bytes), "r") as nested_zf:
                # Once we're inside DOC/**, we keep doc_only=False because member paths
                # inside nested archives may not start with DOC/ anymore.
                yield from _walk_zip(
                    zf=nested_zf,
                    parent_chain=nested_chain,
                    doc_only=False,
                )
        else:
            mode = _tar_mode_from_name(lower)
            with tarfile.open(fileobj=io.BytesIO(nested_bytes), mode=mode) as nested_tf:
                yield from _walk_tar(
                    tf=nested_tf,
                    parent_chain=nested_chain,
                    doc_only=False,
                )


# ----------------------------
# TAR walking
# ----------------------------

def _walk_tar(
    *,
    tf: tarfile.TarFile,
    parent_chain: str,
    doc_only: bool,
) -> Iterator[XmlPayload]:
    members = [m for m in tf.getmembers() if m.isfile()]
    members.sort(key=lambda m: m.name)

    for member in members:
        member_path = member.name

        if doc_only and not _is_under_doc(member_path):
            continue

        extracted = tf.extractfile(member)
        if extracted is None:
            continue
        data = extracted.read()

        lower = member_path.lower()
        if lower.endswith(".xml"):
            source_id = f"{parent_chain}::{member_path}"
            yield XmlPayload(source_id=source_id, xml_bytes=data)
            continue

        nested_kind = _detect_archive_kind_from_name(lower)
        if nested_kind is None:
            continue

        nested_chain = f"{parent_chain}::{member_path}"

        if nested_kind == "zip":
            with zipfile.ZipFile(io.BytesIO(data), "r") as nested_zf:
                yield from _walk_zip(
                    zf=nested_zf,
                    parent_chain=nested_chain,
                    doc_only=False,
                )
        else:
            mode = _tar_mode_from_name(lower)
            with tarfile.open(fileobj=io.BytesIO(data), mode=mode) as nested_tf:
                yield from _walk_tar(
                    tf=nested_tf,
                    parent_chain=nested_chain,
                    doc_only=False,
                )


# ----------------------------
# Helpers
# ----------------------------

def _is_under_doc(member_path: str) -> bool:
    norm = member_path.lstrip("./")
    if norm.startswith("DOC/"):
        return True
    return "/DOC/" in f"/{norm}"

def _detect_archive_kind_from_name(lower_name: str) -> Optional[str]:
    if lower_name.endswith(".zip"):
        return "zip"
    if lower_name.endswith(".tar"):
        return "tar"
    if lower_name.endswith(".tar.gz") or lower_name.endswith(".tgz"):
        return "tar.gz"
    return None

def _tar_mode_from_name(lower_name: str) -> str:
    # tarfile modes for reading: "r:" (uncompressed), "r:gz" (gzip)
    if lower_name.endswith(".tar.gz") or lower_name.endswith(".tgz"):
        return "r:gz"
    return "r:"
