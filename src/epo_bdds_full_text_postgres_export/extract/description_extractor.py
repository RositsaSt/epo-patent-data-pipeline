from __future__ import annotations
import xml.etree.ElementTree as ET
from .text_utils import element_text_preserve_paragraphs, element_text

class DescriptionExtractor:
    """
    Extract the description section from a full-text XML.

    Typically: <description> ... <p>...</p> ... </description>
    """
    def extract_description(self, root: ET.Element) -> str | None:
        """
        Return description text (paragraph-preserving if possible), or None if missing/empty.
        """
        description_element = root.find("description")
        if description_element is None:
            return None

        paragraph_text = element_text_preserve_paragraphs(description_element, paragraph_tag="p")
        if paragraph_text:
            return paragraph_text

        # Fallback: flatten whole description content
        flattened = element_text(description_element)
        return flattened or None