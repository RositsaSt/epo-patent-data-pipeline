from __future__ import annotations

"""
Domain models used across the graph export pipeline.
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class Publication:
    """Core metadata for a single patent publication."""

    publication_id: str
    document_number: str
    country_code: str
    kind_code: str
    publication_date: str
    application_number: str
    language_code: str
    title: str


@dataclass(frozen=True)
class ParsedPatentDocument:
    """
    Parsed representation of a patent document, ready for graph export.
    """

    publication: Publication
    inventors: List[Tuple[str, str]]        # (name, country)
    applicants: List[Tuple[str, str]]       # (organization name, country)
    ipc_classes: List[str]                  # e.g. "G16B 15/00"
    cpc_classes: List[str]
    cited_publications: List[str]           # e.g. "US2009130102A1"

