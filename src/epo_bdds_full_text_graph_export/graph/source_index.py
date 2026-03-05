from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

from .text_normalization import normalize_text


@dataclass
class SourceIndex:
    """
    Indexes join keys derived from extracted node tables (source_id → entity ids).
    """

    source_to_publication_id: Dict[str, str] = field(default_factory=dict)
    source_to_application_id: Dict[str, str] = field(default_factory=dict)

    _source_file_ids_seen: Set[str] = field(default_factory=set)
    _source_file_node_rows: List[dict] = field(default_factory=list)

    def ingest_publications(self, publication_rows: Iterable[dict]) -> None:
        for row in publication_rows:
            pub_id = normalize_text(row.get("pub_id"))
            source_id = normalize_text(row.get("source_id"))
            if not pub_id or not source_id:
                continue

            self.source_to_publication_id.setdefault(source_id, pub_id)

            if source_id not in self._source_file_ids_seen:
                self._source_file_ids_seen.add(source_id)
                self._source_file_node_rows.append({"source_id": source_id})

    def ingest_applications(self, application_rows: Iterable[dict]) -> None:
        for row in application_rows:
            appln_id = normalize_text(row.get("appln_id"))
            source_id = normalize_text(row.get("source_id"))
            if not appln_id or not source_id:
                continue
            self.source_to_application_id.setdefault(source_id, appln_id)

    def source_file_rows(self) -> List[dict]:
        return list(self._source_file_node_rows)