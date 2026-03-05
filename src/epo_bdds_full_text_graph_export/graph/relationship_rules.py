from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .relationship_registry import RelationshipRegistry
from .source_index import SourceIndex
from .text_normalization import normalize_text


@dataclass(frozen=True)
class RelationshipRules:
    """Encapsulates all relationship creation rules (policy)."""

    def add_sourcefile_links(self, *, index: SourceIndex, registry: RelationshipRegistry) -> None:
        for source_id, pub_id in index.source_to_publication_id.items():
            registry.add(
                from_label="Publication", from_key="pub_id", from_id=pub_id,
                rel_type="FROM_SOURCE",
                to_label="SourceFile", to_key="source_id", to_id=source_id,
                source_id=source_id,
            )

    def add_application_publication_links(self, *, index: SourceIndex, registry: RelationshipRegistry) -> None:
        for source_id, pub_id in index.source_to_publication_id.items():
            appln_id = index.source_to_application_id.get(source_id)
            if not appln_id:
                continue
            registry.add(
                from_label="Application", from_key="appln_id", from_id=appln_id,
                rel_type="HAS_PUBLICATION",
                to_label="Publication", to_key="pub_id", to_id=pub_id,
                source_id=source_id,
            )
            registry.add(
                from_label="Publication", from_key="pub_id", from_id=pub_id,
                rel_type="OF_APPLICATION",
                to_label="Application", to_key="appln_id", to_id=appln_id,
                source_id=source_id,
            )

    def add_ipc_links(self, *, ipc_rows: Iterable[dict], index: SourceIndex, registry: RelationshipRegistry) -> None:
        for row in ipc_rows:
            source_id = normalize_text(row.get("source_id"))
            ipc = normalize_text(row.get("ipc_long_code"))
            if not source_id or not ipc:
                continue
            pub_id = index.source_to_publication_id.get(source_id)
            if not pub_id:
                continue
            registry.add(
                from_label="Publication", from_key="pub_id", from_id=pub_id,
                rel_type="HAS_IPC",
                to_label="IPC", to_key="long_code", to_id=ipc,
                source_id=source_id,
            )

    def add_cpc_links(self, *, cpc_rows: Iterable[dict], index: SourceIndex, registry: RelationshipRegistry) -> None:
        for row in cpc_rows:
            source_id = normalize_text(row.get("source_id"))
            cpc = normalize_text(row.get("cpc_long_code"))
            if not source_id or not cpc:
                continue
            pub_id = index.source_to_publication_id.get(source_id)
            if not pub_id:
                continue
            registry.add(
                from_label="Publication", from_key="pub_id", from_id=pub_id,
                rel_type="HAS_CPC",
                to_label="CPC", to_key="long_code", to_id=cpc,
                source_id=source_id,
            )

    def add_applicant_links(self, *, applicant_rows: Iterable[dict], index: SourceIndex, registry: RelationshipRegistry) -> None:
        for row in applicant_rows:
            source_id = normalize_text(row.get("source_id"))
            org_key = normalize_text(row.get("org_key"))
            if not source_id or not org_key:
                continue
            appln_id = index.source_to_application_id.get(source_id)
            if not appln_id:
                continue
            registry.add(
                from_label="Organisation", from_key="org_key", from_id=org_key,
                rel_type="APPLIES_FOR",
                to_label="Application", to_key="appln_id", to_id=appln_id,
                source_id=source_id,
            )

    def add_inventor_links(self, *, inventor_rows: Iterable[dict], index: SourceIndex, registry: RelationshipRegistry) -> None:
        for row in inventor_rows:
            source_id = normalize_text(row.get("source_id"))
            person_key = normalize_text(row.get("person_key"))
            if not source_id or not person_key:
                continue
            appln_id = index.source_to_application_id.get(source_id)
            if not appln_id:
                continue
            registry.add(
                from_label="Person", from_key="person_key", from_id=person_key,
                rel_type="INVENTED",
                to_label="Application", to_key="appln_id", to_id=appln_id,
                source_id=source_id,
            )

    def add_attorney_links(self, *, attorney_rows: Iterable[dict], index: SourceIndex, registry: RelationshipRegistry) -> None:
        for row in attorney_rows:
            source_id = normalize_text(row.get("source_id"))
            person_key = normalize_text(row.get("person_key"))
            if not source_id or not person_key:
                continue
            appln_id = index.source_to_application_id.get(source_id)
            if not appln_id:
                continue
            registry.add(
                from_label="Person", from_key="person_key", from_id=person_key,
                rel_type="REPRESENTS",
                to_label="Application", to_key="appln_id", to_id=appln_id,
                source_id=source_id,
            )