from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class PersonExtractor:
    """
    Extract persons (inventors/applicants/representatives).

    TODO: Implement based on the EP exchange schema:
    typically under bibliographic-data -> parties.
    """

    def extract(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        return []