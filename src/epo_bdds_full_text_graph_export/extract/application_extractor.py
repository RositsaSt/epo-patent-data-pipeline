from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class ApplicationExtractor:
    def extract(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        """
        Extract a minimal application node.

        NOTE: This is still a placeholder. In EP full-text, application identifiers
        are often in bibliographic-data (not always on root attributes).
        """
        #EP11861483A1
        appln_id = xml_root.get("id") or ""
        appln_number = xml_root.get("doc-number") or ""
        appln_country = xml_root.get("country") or ""
        appln_kind_code = xml_root.get("kind") or ""
        filing_date = "" # TODO: parse from bibliographic-data
        #TODO: Remove EP and A1 from the appl_number, and use the country and kind code fields instead. This is because the doc-number field may contain leading zeros that are not stable across different sources, while the combination of country and kind code is more likely to be stable. For example, if the doc-number is "0011861483", it may be represented as "11861483" in some sources, which would cause issues with matching. By using the country and kind code fields, we can ensure that the application identifier is consistent regardless of how the doc-number is formatted
        
        if not appln_number:
            return []

        return [{
            "appln_id": appln_id,
            "appln_number": appln_number,
            "appln_country": appln_country,
            "appln_kind_code": appln_kind_code,
            "filing_date": filing_date,
            "source_id": source_id,
        }]