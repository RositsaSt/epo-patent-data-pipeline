from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from .entity_keys import AttorneyKeyStrategy, InventorKeyStrategy, OrganisationKeyStrategy
from .relationship_models import RelationshipRow
from .relationship_registry import RelationshipRegistry
from .relationship_rules import RelationshipRules
from .row_enrichers import RowEnricher
from .source_index import SourceIndex


@dataclass
class RelationshipBuilder:
    """
    Facade/orchestrator.

    Delegates:
      - enrichment → RowEnricher
      - indexing   → SourceIndex
      - rules      → RelationshipRules
      - storage    → RelationshipRegistry
    """

    organisation_keys: OrganisationKeyStrategy = field(default_factory=OrganisationKeyStrategy)
    inventor_keys: InventorKeyStrategy = field(default_factory=InventorKeyStrategy)
    attorney_keys: AttorneyKeyStrategy = field(default_factory=AttorneyKeyStrategy)

    registry: RelationshipRegistry = field(default_factory=RelationshipRegistry)
    index: SourceIndex = field(default_factory=SourceIndex)
    rules: RelationshipRules = field(default_factory=RelationshipRules)

    def enricher(self) -> RowEnricher:
        return RowEnricher(self.organisation_keys, self.inventor_keys, self.attorney_keys)

    def ingest_publications(self, rows: Iterable[dict]) -> None:
        self.index.ingest_publications(rows)

    def ingest_applications(self, rows: Iterable[dict]) -> None:
        self.index.ingest_applications(rows)

    def build_static_links(self) -> None:
        self.rules.add_sourcefile_links(index=self.index, registry=self.registry)
        self.rules.add_application_publication_links(index=self.index, registry=self.registry)

    def ingest_ipc(self, rows: Iterable[dict]) -> None:
        self.rules.add_ipc_links(ipc_rows=rows, index=self.index, registry=self.registry)

    def ingest_cpc(self, rows: Iterable[dict]) -> None:
        self.rules.add_cpc_links(cpc_rows=rows, index=self.index, registry=self.registry)

    def ingest_applicants(self, enriched_rows: Iterable[dict]) -> None:
        self.rules.add_applicant_links(applicant_rows=enriched_rows, index=self.index, registry=self.registry)

    def ingest_inventors(self, enriched_rows: Iterable[dict]) -> None:
        self.rules.add_inventor_links(inventor_rows=enriched_rows, index=self.index, registry=self.registry)

    def ingest_attorneys(self, enriched_rows: Iterable[dict]) -> None:
        self.rules.add_attorney_links(attorney_rows=enriched_rows, index=self.index, registry=self.registry)

    def source_file_rows(self) -> List[dict]:
        return self.index.source_file_rows()

    def relationship_rows(self) -> List[RelationshipRow]:
        return self.registry.rows()