from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Tuple


XmlItem = Tuple[str, bytes]  # (source_id, xml_bytes)


@dataclass(frozen=True)
class FileSystemXmlSource:
    root_dir: Path
    suffix: str = ".xml"

    def iter_paths(self) -> Iterator[Path]:
        for p in self.root_dir.rglob(f"*{self.suffix}"):
            if p.is_file():
                yield p

    def iter_xml_items(self) -> Iterator[XmlItem]:
        for path in self.iter_paths():
            # source_id should be stable and unique:
            source_id = str(path.relative_to(self.root_dir))
            yield source_id, path.read_bytes()