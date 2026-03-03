from __future__ import annotations

from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET

from ..xml.xml_utils import extract_text_from_element

@dataclass(frozen=True)
class ApplicantExtractor:
    """
    Extract applicant nodes from the EP full-text XML root.
    """
    def extract_applicants(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        applicants: List[dict] = []
        
        sdobi = xml_root.find("SDOBI")
        if sdobi is not None:
            b700 = sdobi.find("B700")
            if b700 is not None:
                b710 = b700.find("B710")
                if b710 is not None:
                    for applicant_element in b710.findall(".//B711"):
                        applicant_name = extract_text_from_element(applicant_element, "snm")
                        applicant_epo_id = extract_text_from_element(applicant_element, "iid")
                        applicant_reference = extract_text_from_element(applicant_element, "irf")
                        applicant_address = extract_text_from_element(applicant_element, "adr/str")
                        applicant_city = extract_text_from_element(applicant_element, "adr/city")
                        applicant_country = extract_text_from_element(applicant_element, "adr/ctry")
                        
                        if applicant_name:
                            applicants.append({
                                "applicant_name": applicant_name,
                                "applicant_epo_id": applicant_epo_id,
                                "applicant_reference": applicant_reference,
                                "applicant_address": applicant_address,
                                "applicant_city": applicant_city,
                                "applicant_country": applicant_country,
                                "source_id": source_id
                            })
        
        return applicants