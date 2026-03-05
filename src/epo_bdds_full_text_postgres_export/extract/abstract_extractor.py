from __future__ import annotations
import xml.etree.ElementTree as ET
from .text_utils import element_text

class AbstractExtractor:
    def extract(self, root: ET.Element, *, lang: str) -> str | None:
        """
        Not all EPO BDDS full-text XMLs include an abstract for all kinds.
        Your sample B1 file has no <abstract>.
        We try a few common patterns and return None if not found.
        """
        # Common: <abstract lang="en">...</abstract>
        abs_el = None
        for cand in root.findall(".//abstract"):
            if cand.get("lang") in (None, "", lang):
                abs_el = cand
                break
        if abs_el is not None:
            txt = element_text(abs_el)
            return txt or None

        # Sometimes abstract is encoded in other structures; keep this conservative.
        return None