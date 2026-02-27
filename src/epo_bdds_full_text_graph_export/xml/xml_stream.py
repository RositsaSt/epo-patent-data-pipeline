from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Tuple

from .xml_source import FileSystemXmlSource, XmlItem


@dataclass(frozen=True)
class XmlStream:
    source: FileSystemXmlSource

    def iter_xml_items(self) -> Iterator[XmlItem]:
        # Optional: stable sort so runs are deterministic (costly for huge dirs).
        for item in self.source.iter_xml_items():
            yield item