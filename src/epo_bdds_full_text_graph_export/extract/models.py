from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


Row = Dict[str, object]


@dataclass(frozen=True)
class GraphRows:
    """
    Container for rows destined for Neo4j CSV tables.
    """
    publications: List[Row] = field(default_factory=list)
    applications: List[Row] = field(default_factory=list)
    persons: List[Row] = field(default_factory=list)
    citations: List[Row] = field(default_factory=list)
    relationships: List[Row] = field(default_factory=list)