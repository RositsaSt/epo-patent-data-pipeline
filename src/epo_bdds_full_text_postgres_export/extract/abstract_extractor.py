from __future__ import annotations
import xml.etree.ElementTree as ET
from .text_utils import element_text

class AbstractExtractor:
    """
    Extract the abstract text for a given language, if present.

    Many BDDS full-text XML files (depending on kind) do not contain <abstract>.
    """
    def extract_abstract(self, root: ET.Element, *, lang: str) -> str | None:
        """
        Return abstract text for the requested language, or None if not found.
        """
        # Common: <abstract lang="en">...</abstract>
        for candidate in root.findall(".//abstract"):
            candidate_lang = (candidate.get("lang") or "").strip()
            if not candidate_lang or candidate_lang == lang:
                text = element_text(candidate)
                return text or None
        
        return None