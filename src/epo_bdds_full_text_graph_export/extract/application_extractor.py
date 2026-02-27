from __future__ import annotations
from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class ApplicationExtractor:
    def extract(self, root: ET.Element, source_id: str) -> list[dict]:
        # TODO: implement real parsing
        # placeholders:
        appl_id = root.get("id") or ""
        appl_number = root.get("doc-number") or ""
        appl_country = root.get("country") or ""
        filing_date = ""

        if not appl_number:
            return []

        return [{
            "appl_id": appl_id,
            "appl_number": appl_number,
            "appl_country": appl_country,
            "filing_date": filing_date,
            "source_id": source_id,
        }]