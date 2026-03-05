from __future__ import annotations
import xml.etree.ElementTree as ET

from ..domain.models import FullTextRecord
from .abstract_extractor import AbstractExtractor
from .description_extractor import DescriptionExtractor
from .claims_extractor import ClaimsExtractor

class FullTextExtractor:
    def __init__(
        self,
        abstract_extractor: AbstractExtractor,
        description_extractor: DescriptionExtractor,
        claims_extractor: ClaimsExtractor,
    ) -> None:
        self._abstract = abstract_extractor
        self._description = description_extractor
        self._claims = claims_extractor

    def extract(self, *, source_id: str, xml_bytes: bytes, lang: str) -> FullTextRecord | None:
        root = ET.fromstring(xml_bytes)

        country = (root.get("country") or "").strip()
        pub_number = (root.get("doc-number") or "").strip()
        kind_code = (root.get("kind") or "").strip()
        appln_id = (root.get("id") or "").strip()
        abstract_text = self._abstract.extract(root, lang=lang)
        description_text = self._description.extract(root)
        claims_text, claims_json = self._claims.extract(root, lang=lang)

        # If absolutely nothing exists, skip
        if not any([abstract_text, description_text, claims_text]):
            return None
        
        if not (country and pub_number and kind_code):
            return []
        
        pub_id = f"{country}{pub_number}{kind_code}"

        return FullTextRecord(
            source_id=source_id,
            appln_id=appln_id,
            pub_id=pub_id,
            lang=lang,
            abstract_text=abstract_text,
            description_text=description_text,
            claims_text=claims_text,
            claims_json=claims_json,
        )