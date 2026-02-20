from __future__ import annotations

"""
XML parsing for EP full‑text patent documents.
"""

from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from .models import ParsedPatentDocument, Publication


class XmlPatentDocumentParser:
    """
    Parse EP patent XML (ep-patent-document) into a ParsedPatentDocument.

    Single responsibility:
        - Understand the XML schema and convert it into a neutral domain model.
    """

    def parse(self, source_id: str, xml_bytes: bytes) -> Optional[ParsedPatentDocument]:
        """
        Parse a single XML document.

        Args:
            source_id: Human‑readable identifier for logging (archive::path).
            xml_bytes: Raw XML bytes.

        Returns:
            ParsedPatentDocument on success, or None if the document is not an
            EP patent document or parsing fails.
        """
        try:
            root = ET.fromstring(xml_bytes)
        except Exception:
            # Caller is responsible for logging; we just signal failure.
            return None

        tag_name = root.tag.split("}")[-1]
        if tag_name != "ep-patent-document":
            return None

        publication = self._parse_publication_metadata(root)
        inventors = self._parse_inventors(root)
        applicants = self._parse_applicants(root)
        ipc_classes = self._parse_ipc_classes(root)
        cpc_classes = self._parse_cpc_classes(root)
        cited_publications = self._parse_citations(root)

        return ParsedPatentDocument(
            publication=publication,
            inventors=inventors,
            applicants=applicants,
            ipc_classes=ipc_classes,
            cpc_classes=cpc_classes,
            cited_publications=cited_publications,
        )

    # ---- element helpers -------------------------------------------------

    @staticmethod
    def _element_text(element: Optional[ET.Element]) -> str:
        """Return stripped element text or an empty string."""
        return (element.text or "").strip() if element is not None and element.text else ""

    @staticmethod
    def _first_child(parent: Optional[ET.Element], xpath: str) -> Optional[ET.Element]:
        """Return the first matching child element, or None."""
        if parent is None:
            return None
        return parent.find(xpath)

    # ---- concrete field parsers ------------------------------------------

    def _parse_publication_metadata(self, root: ET.Element) -> Publication:
        """Extract core publication metadata from the document root."""
        publication_id = (root.get("id") or "").strip()
        document_number = (root.get("doc-number") or "").strip()
        country_code = (root.get("country") or "").strip()
        kind_code = (root.get("kind") or "").strip()
        publication_date = (root.get("date-publ") or "").strip()
        language_code = (root.get("lang") or "").strip() or "en"

        s_dobi = root.find("SDOBI")

        application_number = ""
        if s_dobi is not None:
            b200 = s_dobi.find("B200")
            if b200 is not None:
                application_number = self._element_text(self._first_child(b200, "B210"))

        title = self._parse_title(s_dobi)

        if not publication_id and document_number and country_code and kind_code:
            publication_id = f"{country_code}{document_number}{kind_code}"

        return Publication(
            publication_id=publication_id,
            document_number=document_number,
            country_code=country_code,
            kind_code=kind_code,
            publication_date=publication_date,
            application_number=application_number,
            language_code=language_code,
            title=title,
        )

    def _parse_title(self, s_dobi: Optional[ET.Element]) -> str:
        """
        Parse multilingual titles and return the best one (prefer English).
        """
        if s_dobi is None:
            return ""

        b500 = s_dobi.find("B500")
        if b500 is None:
            return ""

        b540 = b500.find("B540")
        if b540 is None:
            return ""

        titles_by_language: Dict[str, str] = {}
        current_language: Optional[str] = None

        for child in b540:
            local_tag = child.tag.split("}")[-1]
            if local_tag == "B541":
                current_language = self._element_text(child).lower()
            elif local_tag == "B542" and current_language:
                titles_by_language[current_language] = self._element_text(child)
                current_language = None

        if not titles_by_language:
            return ""

        return titles_by_language.get("en") or next(iter(titles_by_language.values()))

    def _parse_inventors(self, root: ET.Element) -> List[Tuple[str, str]]:
        """Return list of (inventor_name, country_code)."""
        inventors: List[Tuple[str, str]] = []
        s_dobi = root.find("SDOBI")
        if s_dobi is None:
            return inventors

        b700 = s_dobi.find("B700")
        if b700 is None:
            return inventors

        b720 = b700.find("B720")
        if b720 is None:
            return inventors

        for inventor_element in b720.findall("B721"):
            name = self._element_text(inventor_element.find("snm"))
            address_element = self._first_child(inventor_element, "adr")
            country_code = self._element_text(self._first_child(address_element, "ctry"))
            if name:
                inventors.append((name, country_code))
        return inventors

    def _parse_applicants(self, root: ET.Element) -> List[Tuple[str, str]]:
        """Return list of (applicant_organization_name, country_code)."""
        applicants: List[Tuple[str, str]] = []
        s_dobi = root.find("SDOBI")
        if s_dobi is None:
            return applicants

        b700 = s_dobi.find("B700")
        if b700 is None:
            return applicants

        b730 = b700.find("B730")
        if b730 is None:
            return applicants

        for applicant_element in b730.findall("B731"):
            name = self._element_text(applicant_element.find("snm"))
            address_element = self._first_child(applicant_element, "adr")
            country_code = self._element_text(self._first_child(address_element, "ctry"))
            if name:
                applicants.append((name, country_code))
        return applicants

    def _parse_ipc_classes(self, root: ET.Element) -> List[str]:
        """Extract IPC classification codes."""
        s_dobi = root.find("SDOBI")
        if s_dobi is None:
            return []

        b500 = s_dobi.find("B500")
        if b500 is None:
            return []

        b510ep = b500.find("B510EP")
        if b510ep is None:
            return []

        ipc_codes: List[str] = []
        for classification in b510ep.findall(".//classification-ipcr"):
            text_element = classification.find("text")
            code = self._normalise_classification_text(self._element_text(text_element))
            if code:
                ipc_codes.append(code)
        return ipc_codes

    def _parse_cpc_classes(self, root: ET.Element) -> List[str]:
        """Extract CPC classification codes."""
        s_dobi = root.find("SDOBI")
        if s_dobi is None:
            return []

        b500 = s_dobi.find("B500")
        if b500 is None:
            return []

        b520ep = b500.find("B520EP")
        if b520ep is None:
            return []

        cpc_codes: List[str] = []
        for classification in b520ep.findall(".//classification-cpc"):
            text_element = classification.find("text")
            code = self._normalise_classification_text(self._element_text(text_element))
            if code:
                cpc_codes.append(code)
        return cpc_codes

    def _parse_citations(self, root: ET.Element) -> List[str]:
        """Return cited publication identifiers from <patcit dnum=\"...\">."""
        cited_publications: List[str] = []
        for patcit_element in root.findall(".//patcit"):
            cited_id = (patcit_element.get("dnum") or "").strip()
            if cited_id:
                cited_publications.append(cited_id)
        return cited_publications

    @staticmethod
    def _normalise_classification_text(raw_text: str) -> str:
        """
        Convert raw classification strings into compact codes.

        Example:
            "G16B  15/00        20190101AFI20250623BHEP"
        becomes:
            "G16B 15/00"
        """
        raw_text = raw_text.strip()
        if not raw_text:
            return ""
        parts = raw_text.split()
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} {parts[1]}"

