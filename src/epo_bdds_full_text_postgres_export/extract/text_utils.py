from __future__ import annotations
import re
import xml.etree.ElementTree as ET

_RE_WS = re.compile(r"\s+")

def element_text(el: ET.Element | None) -> str:
    """
    Extract visible text from an element, including nested inline tags,
    normalizing whitespace.
    """
    if el is None:
        return ""
    txt = "".join(el.itertext())
    txt = _RE_WS.sub(" ", txt).strip()
    return txt

def element_text_preserve_paragraphs(parent: ET.Element | None, *, p_tag: str = "p") -> str:
    """
    Common for <description><p>...</p></description>
    """
    if parent is None:
        return ""
    parts: list[str] = []
    for p in parent.findall(p_tag):
        t = element_text(p)
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip()