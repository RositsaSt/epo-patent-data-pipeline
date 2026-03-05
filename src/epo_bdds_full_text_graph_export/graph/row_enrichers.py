from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .entity_keys import AttorneyKeyStrategy, InventorKeyStrategy, OrganisationKeyStrategy


@dataclass(frozen=True)
class RowEnricher:
    organisation_keys: OrganisationKeyStrategy
    inventor_keys: InventorKeyStrategy
    attorney_keys: AttorneyKeyStrategy

    def enrich_applicants(self, rows: Iterable[dict]) -> List[dict]:
        enriched: List[dict] = []
        for row in rows:
            r = dict(row)
            r["org_key"] = self.organisation_keys.make_key(
                applicant_epo_id=r.get("applicant_epo_id"),
                applicant_name=(r.get("applicant_name") or ""),
                applicant_country=r.get("applicant_country"),
            )
            enriched.append(r)
        return enriched

    def enrich_inventors(self, rows: Iterable[dict]) -> List[dict]:
        enriched: List[dict] = []
        for row in rows:
            r = dict(row)
            r["person_key"] = self.inventor_keys.make_key(
                inventor_name=(r.get("inventor_name") or ""),
                inventor_city=r.get("inventor_city"),
                inventor_country=r.get("inventor_country"),
            )
            enriched.append(r)
        return enriched

    def enrich_attorneys(self, rows: Iterable[dict]) -> List[dict]:
        enriched: List[dict] = []
        for row in rows:
            r = dict(row)
            r["person_key"] = self.attorney_keys.make_key(
                attorney_epo_id=r.get("attorney_epo_id"),
                attorney_name=(r.get("attorney_name") or ""),
                attorney_city=r.get("attorney_city"),
                attorney_country=r.get("attorney_country"),
            )
            enriched.append(r)
        return enriched