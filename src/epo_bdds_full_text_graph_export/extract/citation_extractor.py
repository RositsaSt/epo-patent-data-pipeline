from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class CitationExtractor:
    """
    Extract citations from the document.

    TODO: Implement based on EP schema:
    often under bibliographic-data -> references-cited.
    """

    def extract_citations(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        return []