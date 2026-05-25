from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import xml.etree.ElementTree as ET

from ..xml.xml_utils import extract_text_from_element


@dataclass(frozen=True)
class ApplicationExtractor:
    def extract_application_info(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        """
        Extract a minimal application node from the EP full-text XML root.
        """
        appln_id = (xml_root.get("id") or "").strip()
        appln_country = (xml_root.get("id") or "").strip()[:2]
        appln_number = (xml_root.get("id") or "").strip()[2:10]
        appln_kind_code = (xml_root.get("id") or "").strip()[10:]

        sdobi = (xml_root.find("SDOBI"))
        if sdobi is not None:
            b200 = sdobi.find("B200")
            if b200 is not None:
                b220 = b200.find("B220")
                if b220 is not None:
                    appln_filing_date = extract_text_from_element(b220, "date")

            b400 = sdobi.find("B400")
            if b400 is not None:
                b405 = b400.find("B405")
                if b405 is not None:
                    gazette_date = extract_text_from_element(b405, "date")
                    gazette_issue = extract_text_from_element(b405, "bnum")

        if not appln_id:
            return []

        return [{
            "appln_id": appln_id,
            "appln_country": appln_country,
            "appln_number": appln_number,
            "appln_kind_code": appln_kind_code,
            "appln_filing_date": appln_filing_date,
            "gazette_date": gazette_date,
            "gazette_issue": gazette_issue,
            "source_id": source_id,
        }]
