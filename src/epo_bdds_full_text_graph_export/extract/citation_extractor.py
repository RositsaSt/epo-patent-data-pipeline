from __future__ import annotations
from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class CitationExtractor:
    def extract(self, root: ET.Element, source_id: str) -> list[dict]:
        # TODO parse citations
        return []