from __future__ import annotations

from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET

from ..xml.xml_utils import extract_text_from_element


@dataclass(frozen=True)
class AttorneyRepresentativeExtractor:
    """
    Extract attorney/representative nodes from the EP full-text XML root.
    """    
    def extract_attorney_representative(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        attorneys: List[dict] = []
        
        sdobi = xml_root.find("SDOBI")
        if sdobi is not None:
            b700 = sdobi.find("B700")
            if b700 is not None:
                b740 = b700.find("B740")
                if b740 is not None:
                    for attorney_element in b740.findall(".//B741"):
                        attorney_name = extract_text_from_element(attorney_element, "snm")
                        attorney_sfx = extract_text_from_element(attorney_element, "sfx")
                        attorney_epo_id = extract_text_from_element(attorney_element, "iid")
                        attorney_address = extract_text_from_element(attorney_element, "adr/str")
                        attorney_city = extract_text_from_element(attorney_element, "adr/city")
                        attorney_country = extract_text_from_element(attorney_element, "adr/ctry")
                        
                        if attorney_name:
                            attorneys.append({
                                "attorney_name": attorney_name,
                                "attorney_sfx": attorney_sfx,
                                "attorney_epo_id": attorney_epo_id,
                                "attorney_address": attorney_address,
                                "attorney_city": attorney_city,
                                "attorney_country": attorney_country,
                                "source_id": source_id
                            })
                                
        return attorneys