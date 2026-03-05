from __future__ import annotations
import re
import xml.etree.ElementTree as ET

_WHITESPACE_RE = re.compile(r"\s+")

def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace to single spaces and strip leading/trailing whitespace.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()

def element_text(element: ET.Element | None) -> str:
    """
    Extract visible text from an element (including nested inline tags) and normalize whitespace.

    Returns empty string if element is None.
    """
    if element is None:
        return ""
    combined = "".join(element.itertext())
    combined_normalized = normalize_whitespace(combined)
    return combined_normalized

def element_text_preserve_paragraphs(parent: ET.Element | None, *, paragraph_tag: str = "p") -> str:
    """
    Extract paragraph text from a parent element while preserving paragraph breaks.

    Example: description often contains <p> blocks. We return paragraphs separated by blank lines.
    """
    if parent is None:
        return ""
    
    paragraphs: list[str] = []
    for paragraph in parent.findall(paragraph_tag):
        paragraph_text = element_text(paragraph)
        if paragraph_text:
            paragraphs.append(paragraph_text)
            
    return "\n\n".join(paragraphs).strip()