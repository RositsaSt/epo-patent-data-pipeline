from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set, Tuple

from .relationship_models import RelationshipRow
from .text_normalization import normalize_text


@dataclass
class RelationshipRegistry:
    """
    Stores RelationshipRow objects and deduplicates them.

    Responsibility:
      - validate / normalize
      - dedupe (prevents huge duplicate rel CSVs)
      - append
    """

    _rows: List[RelationshipRow] = field(default_factory=list)
    _seen: Set[Tuple[str, str, str, str, str, str, str, str]] = field(default_factory=set)

    def add(
        self,
        *,
        from_label: str,
        from_key: str,
        from_id: str,
        rel_type: str,
        to_label: str,
        to_key: str,
        to_id: str,
        source_id: str,
    ) -> None:
        from_label_n = normalize_text(from_label)
        from_key_n = normalize_text(from_key)
        from_id_n = normalize_text(from_id)
        rel_type_n = normalize_text(rel_type)
        to_label_n = normalize_text(to_label)
        to_key_n = normalize_text(to_key)
        to_id_n = normalize_text(to_id)
        source_id_n = normalize_text(source_id)

        if not (
            from_label_n
            and from_key_n
            and from_id_n
            and rel_type_n
            and to_label_n
            and to_key_n
            and to_id_n
        ):
            return

        dedupe_key = (
            from_label_n,
            from_key_n,
            from_id_n,
            rel_type_n,
            to_label_n,
            to_key_n,
            to_id_n,
            source_id_n,
        )
        if dedupe_key in self._seen:
            return

        self._seen.add(dedupe_key)
        self._rows.append(
            RelationshipRow(
                from_label=from_label_n,
                from_key=from_key_n,
                from_id=from_id_n,
                rel_type=rel_type_n,
                to_label=to_label_n,
                to_key=to_key_n,
                to_id=to_id_n,
                source_id=source_id_n,
            )
        )

    def rows(self) -> List[RelationshipRow]:
        return list(self._rows)