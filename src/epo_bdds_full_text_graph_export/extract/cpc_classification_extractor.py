from __future__ import annotations

from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET

@dataclass(frozen=True)
class CpcClassificationExtractor:
    """
    Extract CPC classification nodes from the EP full-text XML root.
    """
    def extract_cpc_classifications(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        cpc_classification_codes: List[str] = []

        sdobi = xml_root.find("SDOBI")
        if sdobi is not None:
            b500 = sdobi.find("B500")
            if b500 is not None:
                b520ep = b500.find("B520EP")
                if b520ep is not None:
                    for cpc_classification_element in b520ep.findall(".//classification-cpc"):
                        cpc_text_element = cpc_classification_element.find("text")
                        if cpc_text_element is not None:
                            cpc_raw_code = (cpc_text_element.text or "").strip()
                            cpc_long_code = self._normalise_cpc_classification_text((cpc_text_element.text or "").strip())
                            cpc_short_code = cpc_long_code[:4]
                            cpc_classification_codes.append({
                                "cpc_raw_code": cpc_raw_code,
                                "cpc_long_code": cpc_long_code,
                                "cpc_short_code": cpc_short_code,
                                "source_id": source_id,
                            })

        return cpc_classification_codes

    @staticmethod
    def _normalise_cpc_classification_text(raw_text: str) -> str:
        """
        Convert raw cpc classification strings into compact codes.
        """
        raw_text = raw_text.strip()
        if not raw_text:
            return ""
        raw_text_parts = raw_text.split()
        if not raw_text_parts:
            return ""
        if len(raw_text_parts) == 1 or len(raw_text_parts) == 2:
            return raw_text_parts[0]
        if len(raw_text_parts) == 3:
            return raw_text_parts[0]
        return f"{raw_text_parts[0]} {raw_text_parts[1]}"
