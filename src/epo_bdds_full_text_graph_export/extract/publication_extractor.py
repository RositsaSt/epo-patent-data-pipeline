from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class PublicationExtractor:
    """
    Extract a minimal publication node from the EP full-text XML root.

    This implementation reads attributes from the <ep-patent-document> root:
      - country (country code, e.g. EP)
      - doc-number (publication number without country/kind)
      - kind (kind code, e.g. A1)
      - date-publ (publication date)

    It produces one row with a stable pub_id: "{country}{doc_number}{kind}".
    """
    def extract_publication_info(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        country = (xml_root.get("country") or "").strip()
        pub_number = (xml_root.get("doc-number") or "").strip()
        kind_code = (xml_root.get("kind") or "").strip()
        publication_date = (xml_root.get("date-publ") or "").strip()
        pub_language = (xml_root.get("lang") or "").strip()

        if not (country and pub_number and kind_code):
            return []

        pub_id = f"{country}{pub_number}{kind_code}"    
                    
        return [{
            "pub_id": pub_id,
            "country": country,
            "pub_number": pub_number,
            "kind_code": kind_code,
            "publication_date": publication_date,
            "pub_language": pub_language,
            "source_id": source_id,
        }]