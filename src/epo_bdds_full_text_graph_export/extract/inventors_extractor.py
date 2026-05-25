from __future__ import annotations

from dataclasses import dataclass
from email.policy import default
from typing import List
import xml.etree.ElementTree as ET

from ..xml.xml_utils import extract_text_from_element


@dataclass(frozen=True)
class InventorExtractor:
    """
    Extract inventor nodes from the EP full-text XML root.
    """
    def extract_inventors(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        inventors: List[dict] = []

        sdobi = xml_root.find("SDOBI")
        if sdobi is not None:
            b700 = sdobi.find("B700")
            if b700 is not None:
                b720 = b700.find("B720")
                if b720 is not None:
                    for inventor_element in b720.findall(".//B721"):
                        inventor_name = extract_text_from_element(inventor_element, "snm")
                        inventor_address = extract_text_from_element(inventor_element, "adr/str")
                        inventor_city = extract_text_from_element(inventor_element, "adr/city")
                        inventor_country = extract_text_from_element(inventor_element, "adr/ctry")

                        if inventor_name:
                            inventors.append({
                                "inventor_name": inventor_name,
                                "inventor_address": inventor_address,
                                "inventor_city": inventor_city,
                                "inventor_country": inventor_country,
                                "source_id": source_id
                            })

        return inventors
