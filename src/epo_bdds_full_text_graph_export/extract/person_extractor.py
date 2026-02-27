from __future__ import annotations
from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class PersonExtractor:
    def extract(self, root: ET.Element, source_id: str) -> list[dict]:
        # TODO parse real parties
        return []