from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol, Tuple

from .archive_walk import iter_doc_xml_from_top_archive


XmlItem=Tuple[str, bytes]  # (source_id, xml_bytes)

class XmlSource(Protocol):
    """Anything that can stream XML documents as (source_id, xml_bytes)."""
    def iter_xml_items(self) -> Iterator[XmlItem]: ...

    
@dataclass(frozen=True)
class FileSystemXmlSource:
    """
    Streams *.xml files from a directory tree.

    source_id is the relative path from root_dir, which is stable if the tree
    is stable.
    """
    root_dir: Path
    file_suffix: str = ".xml"
    def iter_xml_items(self) -> Iterator[XmlItem]:
        for xml_path in self._iter_xml_paths():
            source_id = str(xml_path.relative_to(self.root_dir))
            yield source_id, xml_path.read_bytes()
                
                
    def iter_xml_paths(self) -> Iterator[Path]:
        for path in self.root_dir.rglob(f"*{self.file_suffix}"):
            if path.is_file():
                yield path


@dataclass(frozen=True)
class BddsNestedArchiveXmlSource:
    """
    Streams XMLs from a directory of BDDS delivery archives (zip/tar/tar.gz/tgz).

    Each top-level archive is traversed under DOC/** and nested archives are
    opened recursively.
    """
    top_archives_dir: Path
    def iter_xml_items(self) -> Iterator[XmlItem]:
        for top_archive in self._iter_top_archives():
            for payload in iter_doc_xml_from_top_archive(top_archive):
                yield payload.source_id, payload.xml_bytes

    def _iter_top_archives(self) -> Iterator[Path]:
        if not self.top_archives_dir.exists():
            raise FileNotFoundError(f"Top archives dir does not exist: {self.top_archives_dir}")

        candidates = []
        for path in self.top_archives_dir.iterdir():
            if not path.is_file():
                continue
            name = path.name.lower()
            if name.endswith(".zip") or name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz"):
                candidates.append(path)

        for path in sorted(candidates, key=lambda p: p.name):
            yield path