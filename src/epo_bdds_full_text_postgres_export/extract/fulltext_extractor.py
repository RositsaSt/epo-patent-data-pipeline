from __future__ import annotations

import xml.etree.ElementTree as ET

from ..domain.models import FullTextRecord
from .abstract_extractor import AbstractExtractor
from .description_extractor import DescriptionExtractor
from .claims_extractor import ClaimsExtractor


class FullTextExtractor:
    """
    High-level extractor that produces a FullTextRecord from raw XML bytes.

    Responsibility:
      - parse XML bytes
      - compute pub_id and appln_id
      - delegate section extraction to specialized extractors
    """
    def __init__(
        self,
        abstract_extractor: AbstractExtractor,
        description_extractor: DescriptionExtractor,
        claims_extractor: ClaimsExtractor,
    ) -> None:
        self._abstract_extractor = abstract_extractor
        self._description_extractor = description_extractor
        self._claims_extractor = claims_extractor

    def extract_record(self, *, source_id: str, xml_bytes: bytes, lang: str) -> FullTextRecord | None:
        """
        Extract a FullTextRecord for the given language.

        Returns None if the document has none of the target sections (abstract/description/claims)
        for that language.
        """
        root = ET.fromstring(xml_bytes)

        country = (root.get("country") or "").strip()
        pub_number = (root.get("doc-number") or "").strip()
        kind_code = (root.get("kind") or "").strip()
        appln_id = (root.get("id") or "").strip()
        
        if not (country and pub_number and kind_code):
            return None

        pub_id = f"{country}{pub_number}{kind_code}"
        
        abstract_text = self._abstract_extractor.extract_abstract(root, lang=lang)
        description_text = self._description_extractor.extract_description(root)
        claims_text, claims_json = self._claims_extractor.extract_claims(root, lang=lang)

        if not any([abstract_text, description_text, claims_text]):
            return None

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