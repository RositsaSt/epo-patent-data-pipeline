from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class GraphRows:
    publications: list[dict]
    applications: list[dict]
    persons: list[dict]
    citations: list[dict]
    relationships: list[dict]