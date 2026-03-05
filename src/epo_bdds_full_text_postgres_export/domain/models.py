from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FullTextRecord:
    """
    Represents extracted full-text content for a single publication id and language.
    """
    source_id: str
    pub_id: str
    appln_id: str
    lang: str
    abstract_text: str | None
    description_text: str | None
    claims_text: str | None
    claims_json: list[dict[str, Any]] | None