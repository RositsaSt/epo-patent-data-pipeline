from __future__ import annotations
import xml.etree.ElementTree as ET
from .text_utils import element_text_preserve_paragraphs, element_text

class DescriptionExtractor:
    def extract(self, root: ET.Element) -> str | None:
        desc = root.find("description")
        if desc is None:
            return None

        # In your sample EP16805412... it's <description><p>...</p>...
        txt = element_text_preserve_paragraphs(desc, p_tag="p")
        if txt:
            return txt

        # Fallback: flatten
        flat = element_text(desc)
        return flat or None