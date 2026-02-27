from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .xml_source import XmlItem, XmlSource


@dataclass(frozen=True)
class XmlStream:
    """
    A thin streaming wrapper that yields XML items from an XmlSource.

    This class exists to keep the pipeline wiring readable and to allow
    future additions like ordering, filtering, metrics, etc.
    """
    source: XmlSource

    def iter_xml_items(self) -> Iterator[XmlItem]:
        yield from self.source.iter_xml_items()