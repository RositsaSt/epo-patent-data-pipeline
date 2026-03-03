from __future__ import annotations

from dataclasses import dataclass
from typing import List
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class IpcClassificationExtractor:
    """
    Extract classification nodes (IPC, CPC) from the EP full-text XML root.    
    """
    def extract_ipc_classifications(self, xml_root: ET.Element, source_id: str) -> list[dict]:
        ipc_classification_codes: List[dict] = []
        
        sdobi = xml_root.find("SDOBI")
        if sdobi is not None:
            b500 = sdobi.find("B500")
            if b500 is not None:
                b510ep = b500.find("B510EP")
                if b510ep is not None:
                    for ipc_classification_element in b510ep.findall(".//classification-ipcr"):
                        ipc_text_element = ipc_classification_element.find("text")
                        if ipc_text_element is not None:
                            ipc_raw_code = (ipc_text_element.text or "").strip()
                            ipc_long_code = self._normalise_ipc_classification_text((ipc_text_element.text or "").strip())
                            ipc_short_code = ipc_long_code.split()[0]
                            ipc_classification_codes.append({
                                "ipc_raw_code": ipc_raw_code,
                                "ipc_long_code": ipc_long_code,
                                "ipc_short_code": ipc_short_code,
                                "source_id": source_id,
                            })
                            
                                                                
        return ipc_classification_codes
    
    @staticmethod
    def _normalise_ipc_classification_text(raw_text: str) -> str:
        """
        Convert raw ipc classification strings into compact codes.

        Example:
            "G16B  15/00        20190101AFI20250623BHEP"
        becomes:
            "G16B 15/00"
        """
        raw_text = raw_text.strip()
        if not raw_text:
            return ""
        raw_text_parts = raw_text.split()
        if not raw_text_parts:
            return ""
        if len(raw_text_parts) == 1:
            return raw_text_parts[0]
        return f"{raw_text_parts[0]} {raw_text_parts[1]}"