from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class PublicationExtractor:
    def extract(self, root: ET.Element, source_id: str) -> list[dict]:
        country = root.get("country") or ""
        doc_number = root.get("doc-number") or ""
        kind_code = root.get("kind") or ""
        publication_date = root.get("date-publ") or ""

        if not (country and doc_number and kind_code):
            return []

        pub_id = f"{country}{doc_number}{kind_code}"
        return [{
            "pub_id": pub_id,
            "country": country,
            "doc_number": doc_number,
            "kind": kind_code,
            "publication_date": publication_date,
            "source_id": source_id,
        }]