from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RelationshipRow:
    """
    Generic relationship row for Neo4j import.

    Example:
      (from_label {from_key: from_id})-[:rel_type {source_id}]->(to_label {to_key: to_id})

    Fields:
      - from_label: start node label
      - from_key:   start node key property name
      - from_id:    start node key value
      - rel_type:   relationship type
      - to_label:   end node label
      - to_key:     end node key property name
      - to_id:      end node key value
      - source_id:  provenance/join key (e.g., XML file id)
    """

    from_label: str
    from_key: str
    from_id: str
    rel_type: str
    to_label: str
    to_key: str
    to_id: str
    source_id: str

    def as_dict(self) -> dict:
        return {
            "from_label": self.from_label,
            "from_key": self.from_key,
            "from_id": self.from_id,
            "rel_type": self.rel_type,
            "to_label": self.to_label,
            "to_key": self.to_key,
            "to_id": self.to_id,
            "source_id": self.source_id,
        }