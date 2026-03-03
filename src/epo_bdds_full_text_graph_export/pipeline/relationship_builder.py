from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Set, Tuple


class RelType(str, Enum):
    HAS_PUBLICATION = "HAS_PUBLICATION"
    OF_APPLICATION = "OF_APPLICATION"
    HAS_IPC = "HAS_IPC"
    HAS_CPC = "HAS_CPC"
    FROM_SOURCE = "FROM_SOURCE"
    APPLIES_FOR = "APPLIES_FOR"
    INVENTED = "INVENTED"
    REPRESENTS = "REPRESENTS"


def _norm(s: Optional[str]) -> str:
    return (s or "").strip()


def _norm_lower(s: Optional[str]) -> str:
    return _norm(s).lower()


def make_org_key(applicant_epo_id: Optional[str], applicant_name: str, applicant_country: Optional[str]) -> str:
    epo = _norm(applicant_epo_id)
    if epo:
        return f"EPO:{epo}"
    # fallback: name + country
    return f"NAME:{_norm_lower(applicant_name)}|CC:{_norm(applicant_country)}"


def make_person_key(
    epo_id: Optional[str],
    name: str,
    city: Optional[str],
    country: Optional[str],
    *,
    role_prefix: str = "PERSON",
) -> str:
    epo = _norm(epo_id)
    if epo:
        return f"EPO:{epo}"
    # fallback: name + city + country (+ role to reduce collisions between inventor/attorney)
    return f"{role_prefix}:NAME:{_norm_lower(name)}|CITY:{_norm_lower(city)}|CC:{_norm(country)}"


@dataclass(frozen=True)
class RelationshipRow:
    """
    Generic relationship row you can write to relationships.csv.

    Matches your schema:
      relationships_fields=["from_id","to_id","rel_type","source_id"]

    Notes:
    - from_id / to_id must match the *merge keys* you will use in Neo4j for each label.
      e.g. Publication.pub_id, Application.appln_id, IPC.long_code, CPC.long_code, SourceFile.source_id,
      Organisation.org_key, Person.person_key
    - rel_type is a string (enum-backed).
    """
    from_id: str
    to_id: str
    rel_type: str
    source_id: str


class RelationshipBuilder:
    """
    Builds graph relationships deterministically from your already-parsed CSV rows.

    Input expectations:
    - publications rows provide (pub_id, source_id)
    - applications rows provide (appln_id, source_id)
    - other rows provide source_id, and we resolve:
        source_id -> pub_id -> appln_id
    - citations rows already provide from_pub_id/to_pub_id

    Produces:
    - RelationshipRow list suitable for writing to relationships.csv
      with fields: from_id,to_id,rel_type,source_id
    """

    def __init__(self) -> None:
        self._rows: List[RelationshipRow] = []
        self._seen: Set[Tuple[str, str, str, str]] = set()  # dedupe

        # lookup maps
        self._source_to_pub_id: Dict[str, str] = {}
        self._source_to_appln_id: Dict[str, str] = {}

    # ----------------------------
    # Public API
    # ----------------------------

    def ingest_publications(self, publication_rows: Iterable[dict]) -> None:
        """
        Builds source_id -> pub_id mapping and adds Publication -> SourceFile edges.
        """
        for r in publication_rows:
            pub_id = _norm(r.get("pub_id"))
            source_id = _norm(r.get("source_id"))
            if not pub_id or not source_id:
                continue

            # If duplicates happen, keep first; you can also choose to overwrite.
            self._source_to_pub_id.setdefault(source_id, pub_id)

            # (:Publication)-[:FROM_SOURCE]->(:SourceFile)
            self._add(pub_id, source_id, RelType.FROM_SOURCE, source_id)

    def ingest_applications(self, application_rows: Iterable[dict]) -> None:
        """
        Builds source_id -> appln_id mapping.
        """
        for r in application_rows:
            appln_id = _norm(r.get("appln_id"))
            source_id = _norm(r.get("source_id"))
            if not appln_id or not source_id:
                continue
            self._source_to_appln_id.setdefault(source_id, appln_id)

    def link_applications_publications(self) -> None:
        """
        Uses the source_id join to connect:
        (:Application)-[:HAS_PUBLICATION]->(:Publication)
        (:Publication)-[:OF_APPLICATION]->(:Application)

        Call this after ingest_publications() and ingest_applications().
        """
        # iterate over intersection of sources we know in both maps
        for source_id, pub_id in self._source_to_pub_id.items():
            appln_id = self._source_to_appln_id.get(source_id)
            if not appln_id:
                continue

            self._add(appln_id, pub_id, RelType.HAS_PUBLICATION, source_id)
            self._add(pub_id, appln_id, RelType.OF_APPLICATION, source_id)

    def ingest_ipc(self, ipc_rows: Iterable[dict]) -> None:
        """
        Adds (:Publication)-[:HAS_IPC]->(:IPC) edges.
        Uses ipc_long_code as the IPC node key.
        """
        for r in ipc_rows:
            source_id = _norm(r.get("source_id"))
            ipc_long = _norm(r.get("ipc_long_code"))
            if not source_id or not ipc_long:
                continue
            pub_id = self._source_to_pub_id.get(source_id)
            if not pub_id:
                continue
            self._add(pub_id, ipc_long, RelType.HAS_IPC, source_id)

    def ingest_cpc(self, cpc_rows: Iterable[dict]) -> None:
        """
        Adds (:Publication)-[:HAS_CPC]->(:CPC) edges.
        Uses cpc_long_code as the CPC node key.
        """
        for r in cpc_rows:
            source_id = _norm(r.get("source_id"))
            cpc_long = _norm(r.get("cpc_long_code"))
            if not source_id or not cpc_long:
                continue
            pub_id = self._source_to_pub_id.get(source_id)
            if not pub_id:
                continue
            self._add(pub_id, cpc_long, RelType.HAS_CPC, source_id)

    def ingest_applicants(self, applicant_rows: Iterable[dict]) -> None:
        """
        Adds (:Organisation)-[:APPLIES_FOR]->(:Application) edges.

        Organisation key strategy:
        - prefer applicant_epo_id if present
        - else fallback to normalized name + country
        """
        for r in applicant_rows:
            source_id = _norm(r.get("source_id"))
            name = _norm(r.get("applicant_name"))
            if not source_id or not name:
                continue

            appln_id = self._source_to_appln_id.get(source_id)
            if not appln_id:
                continue

            org_key = make_org_key(
                r.get("applicant_epo_id"),
                name,
                r.get("applicant_country"),
            )
            self._add(org_key, appln_id, RelType.APPLIES_FOR, source_id)

    def ingest_inventors(self, inventor_rows: Iterable[dict]) -> None:
        """
        Adds (:Person)-[:INVENTED]->(:Application) edges.

        Person key strategy:
        - inventors have no epo_id in your schema, so use fallback:
          name + city + country (+ role prefix INVENTOR)
        """
        for r in inventor_rows:
            source_id = _norm(r.get("source_id"))
            name = _norm(r.get("inventor_name"))
            if not source_id or not name:
                continue

            appln_id = self._source_to_appln_id.get(source_id)
            if not appln_id:
                continue

            person_key = make_person_key(
                epo_id=None,
                name=name,
                city=r.get("inventor_city"),
                country=r.get("inventor_country"),
                role_prefix="INVENTOR",
            )
            self._add(person_key, appln_id, RelType.INVENTED, source_id)

    def ingest_attorneys(self, attorney_rows: Iterable[dict]) -> None:
        """
        Adds (:Person)-[:REPRESENTS]->(:Application) edges.

        Person key strategy:
        - prefer attorney_epo_id if present
        - else fallback to name + city + country (+ role prefix ATTORNEY)
        """
        for r in attorney_rows:
            source_id = _norm(r.get("source_id"))
            name = _norm(r.get("attorney_name"))
            if not source_id or not name:
                continue

            appln_id = self._source_to_appln_id.get(source_id)
            if not appln_id:
                continue

            person_key = make_person_key(
                epo_id=r.get("attorney_epo_id"),
                name=name,
                city=r.get("attorney_city"),
                country=r.get("attorney_country"),
                role_prefix="ATTORNEY",
            )
            self._add(person_key, appln_id, RelType.REPRESENTS, source_id)

    def ingest_citations(self, citation_rows: Iterable[dict]) -> None:
        """
        Optional: adds (:Publication)-[:CITES {cite_type}]->(:Publication)

        Your relationships schema doesn't include relationship properties (cite_type),
        so if you want citations, either:
        - keep them in citations.csv and import separately, OR
        - encode cite_type into rel_type (not recommended)

        Here we *do nothing* by default to avoid losing cite_type.
        """
        return

    def rows(self) -> List[RelationshipRow]:
        return list(self._rows)

    # ----------------------------
    # Internals
    # ----------------------------

    def _add(self, from_id: str, to_id: str, rel_type: RelType, source_id: str) -> None:
        from_id = _norm(from_id)
        to_id = _norm(to_id)
        source_id = _norm(source_id)
        if not from_id or not to_id:
            return

        key = (from_id, to_id, str(rel_type.value), source_id)
        if key in self._seen:
            return
        self._seen.add(key)
        self._rows.append(
            RelationshipRow(
                from_id=from_id,
                to_id=to_id,
                rel_type=str(rel_type.value),
                source_id=source_id,
            )
        )