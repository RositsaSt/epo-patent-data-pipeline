from __future__ import annotations

import xml.etree.ElementTree as ET


def extract_text_from_element(
    root_element: ET.Element,
    xpath_expression: str,
    *,
    default: str = "",
) -> str:
    matched_element = root_element.find(xpath_expression)
    if matched_element is None or matched_element.text is None:
        return default
    return matched_element.text.strip()


def extract_text_from_element_ns(
    root_element: ET.Element,
    xpath_expression: str,
    *,
    namespaces: dict[str, str],
    default: str = "",
) -> str:
    matched_element = root_element.find(xpath_expression, namespaces=namespaces)
    if matched_element is None or matched_element.text is None:
        return default
    return matched_element.text.strip()