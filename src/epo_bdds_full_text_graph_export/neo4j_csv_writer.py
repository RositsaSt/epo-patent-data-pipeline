from __future__ import annotations

"""
CSV writer for Neo4j bulk import.

Responsible for:
- Writing node CSVs (Publication, Person, Organization, IPCClass, CPCClass)
- Writing relationship CSVs (INVENTED_BY, OWNED_BY, HAS_IPC, HAS_CPC, CITES)
- De-duplicating nodes (and optionally relationships)
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, TextIO, Tuple

from .models import ParsedPatentDocument, Publication


def _norm_text(s: str) -> str:
    # Minimal normalization to reduce accidental duplicates
    return " ".join(s.strip().split())


def _norm_code(s: str) -> str:
    return _norm_text(s).upper()


@dataclass(frozen=True)
class _CsvSink:
    writer: csv.DictWriter
    fh: TextIO


class Neo4jCsvGraphWriter:
    """
    Write parsed patent documents into Neo4j bulk-importable CSV files.

    Single responsibility:
      - Transform ParsedPatentDocument instances into rows across node and
        relationship CSVs, handling de-duplication.
    """

    def __init__(self, output_directory: Path, *, dedupe_relationships: bool = True) -> None:
        self._output_directory = output_directory
        self._dedupe_relationships = dedupe_relationships

        # Node de-duplication state
        self._seen_publication_ids: Set[str] = set()
        self._person_key_to_id: Dict[Tuple[str, str], str] = {}
        self._organization_key_to_id: Dict[Tuple[str, str], str] = {}
        self._seen_ipc_codes: Set[str] = set()
        self._seen_cpc_codes: Set[str] = set()

        # Relationship de-duplication state (optional)
        self._seen_pub_person: Set[Tuple[str, str]] = set()
        self._seen_pub_org: Set[Tuple[str, str]] = set()
        self._seen_pub_ipc: Set[Tuple[str, str]] = set()
        self._seen_pub_cpc: Set[Tuple[str, str]] = set()
        self._seen_pub_cites: Set[Tuple[str, str]] = set()

        self._person_counter = 0
        self._organization_counter = 0

        # Create sinks
        self._sinks: Dict[str, _CsvSink] = {}

        self._publication = self._create_sink(
            "nodes_publication.csv",
            [
                "pub_id:ID(PatentPublication)",
                "doc_number:string",
                "country:string",
                "kind:string",
                "date_publ:string",
                "appln_id:string",
                "lang:string",
                "title:string",
            ],
        )
        self._person = self._create_sink(
            "nodes_person.csv",
            [
                "person_id:ID(Person)",
                "name:string",
                "country:string",
            ],
        )
        self._organization = self._create_sink(
            "nodes_organization.csv",
            [
                "org_id:ID(Organization)",
                "name:string",
                "country:string",
            ],
        )
        self._ipc = self._create_sink(
            "nodes_ipc.csv",
            ["ipc_code:ID(IPCClass)"],
        )
        self._cpc = self._create_sink(
            "nodes_cpc.csv",
            ["cpc_code:ID(CPCClass)"],
        )

        self._rel_pub_inventor = self._create_sink(
            "rel_pub_inventor.csv",
            [":START_ID(PatentPublication)", ":END_ID(Person)", ":TYPE"],
        )
        self._rel_pub_applicant = self._create_sink(
            "rel_pub_applicant.csv",
            [":START_ID(PatentPublication)", ":END_ID(Organization)", ":TYPE"],
        )
        self._rel_pub_ipc = self._create_sink(
            "rel_pub_ipc.csv",
            [":START_ID(PatentPublication)", ":END_ID(IPCClass)", ":TYPE"],
        )
        self._rel_pub_cpc = self._create_sink(
            "rel_pub_cpc.csv",
            [":START_ID(PatentPublication)", ":END_ID(CPCClass)", ":TYPE"],
        )
        self._rel_pub_cites = self._create_sink(
            "rel_pub_cites_pub.csv",
            [":START_ID(PatentPublication)", ":END_ID(PatentPublication)", ":TYPE"],
        )

        self._closed = False

    # ----- context manager -------------------------------------------------

    def __enter__(self) -> "Neo4jCsvGraphWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---- public API ------------------------------------------------------

    def write_document(self, document: ParsedPatentDocument) -> None:
        """Write a single parsed patent document to node and relationship CSVs."""
        publication = document.publication
        self._write_publication_if_new(publication)

        self._write_inventors(document)
        self._write_applicants(document)
        self._write_ipc_classes(document)
        self._write_cpc_classes(document)
        self._write_citations(document)

    def close(self) -> None:
        """Flush and close all CSV files."""
        if self._closed:
            return
        # Make sure OS buffers are flushed
        for sink in self._sinks.values():
            try:
                sink.fh.flush()
            finally:
                sink.fh.close()
        self._closed = True

    # ---- writer helpers --------------------------------------------------

    def _create_sink(self, file_name: str, fieldnames: List[str]) -> _CsvSink:
        file_path = self._output_directory / file_name
        file_path.parent.mkdir(parents=True, exist_ok=True)

        fh = file_path.open("w", newline="", encoding="utf-8")
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        sink = _CsvSink(writer=writer, fh=fh)
        self._sinks[file_name] = sink
        return sink

    # ---- node writers ----------------------------------------------------

    def _write_publication_if_new(self, publication: Publication) -> None:
        pub_id = _norm_text(publication.publication_id)
        if pub_id in self._seen_publication_ids:
            return

        self._seen_publication_ids.add(pub_id)
        self._publication.writer.writerow(
            {
                "pub_id:ID(PatentPublication)": pub_id,
                "doc_number:string": _norm_text(publication.document_number),
                "country:string": _norm_code(publication.country_code),
                "kind:string": _norm_code(publication.kind_code),
                "date_publ:string": _norm_text(publication.publication_date),
                "appln_id:string": _norm_text(publication.application_number),
                "lang:string": _norm_code(publication.language_code),
                "title:string": _norm_text(publication.title),
            }
        )

    def _get_or_create_person_id(self, name: str, country_code: str) -> str:
        key = (_norm_text(name), _norm_code(country_code))
        person_id = self._person_key_to_id.get(key)
        if person_id is None:
            self._person_counter += 1
            person_id = f"person_{self._person_counter:06d}"
            self._person_key_to_id[key] = person_id
            self._person.writer.writerow(
                {
                    "person_id:ID(Person)": person_id,
                    "name:string": key[0],
                    "country:string": key[1],
                }
            )
        return person_id

    def _get_or_create_org_id(self, org_name: str, country_code: str) -> str:
        key = (_norm_text(org_name), _norm_code(country_code))
        org_id = self._organization_key_to_id.get(key)
        if org_id is None:
            self._organization_counter += 1
            org_id = f"org_{self._organization_counter:06d}"
            self._organization_key_to_id[key] = org_id
            self._organization.writer.writerow(
                {
                    "org_id:ID(Organization)": org_id,
                    "name:string": key[0],
                    "country:string": key[1],
                }
            )
        return org_id

    # ---- relationship writers -------------------------------------------

    def _write_inventors(self, document: ParsedPatentDocument) -> None:
        pub_id = _norm_text(document.publication.publication_id)

        for name, country_code in document.inventors:
            person_id = self._get_or_create_person_id(name, country_code)
            edge = (pub_id, person_id)
            if self._dedupe_relationships and edge in self._seen_pub_person:
                continue
            self._seen_pub_person.add(edge)

            self._rel_pub_inventor.writer.writerow(
                {
                    ":START_ID(PatentPublication)": pub_id,
                    ":END_ID(Person)": person_id,
                    ":TYPE": "INVENTED_BY",
                }
            )

    def _write_applicants(self, document: ParsedPatentDocument) -> None:
        pub_id = _norm_text(document.publication.publication_id)

        for org_name, country_code in document.applicants:
            org_id = self._get_or_create_org_id(org_name, country_code)
            edge = (pub_id, org_id)
            if self._dedupe_relationships and edge in self._seen_pub_org:
                continue
            self._seen_pub_org.add(edge)

            self._rel_pub_applicant.writer.writerow(
                {
                    ":START_ID(PatentPublication)": pub_id,
                    ":END_ID(Organization)": org_id,
                    ":TYPE": "OWNED_BY",
                }
            )

    def _write_ipc_classes(self, document: ParsedPatentDocument) -> None:
        pub_id = _norm_text(document.publication.publication_id)

        for ipc in document.ipc_classes:
            ipc_code = _norm_code(ipc)
            if ipc_code not in self._seen_ipc_codes:
                self._seen_ipc_codes.add(ipc_code)
                self._ipc.writer.writerow({"ipc_code:ID(IPCClass)": ipc_code})

            edge = (pub_id, ipc_code)
            if self._dedupe_relationships and edge in self._seen_pub_ipc:
                continue
            self._seen_pub_ipc.add(edge)

            self._rel_pub_ipc.writer.writerow(
                {
                    ":START_ID(PatentPublication)": pub_id,
                    ":END_ID(IPCClass)": ipc_code,
                    ":TYPE": "HAS_IPC",
                }
            )

    def _write_cpc_classes(self, document: ParsedPatentDocument) -> None:
        pub_id = _norm_text(document.publication.publication_id)

        for cpc in document.cpc_classes:
            cpc_code = _norm_code(cpc)
            if cpc_code not in self._seen_cpc_codes:
                self._seen_cpc_codes.add(cpc_code)
                self._cpc.writer.writerow({"cpc_code:ID(CPCClass)": cpc_code})

            edge = (pub_id, cpc_code)
            if self._dedupe_relationships and edge in self._seen_pub_cpc:
                continue
            self._seen_pub_cpc.add(edge)

            self._rel_pub_cpc.writer.writerow(
                {
                    ":START_ID(PatentPublication)": pub_id,
                    ":END_ID(CPCClass)": cpc_code,
                    ":TYPE": "HAS_CPC",
                }
            )

    def _write_citations(self, document: ParsedPatentDocument) -> None:
        pub_id = _norm_text(document.publication.publication_id)

        for cited in document.cited_publications:
            cited_id = _norm_text(cited)
            edge = (pub_id, cited_id)
            if self._dedupe_relationships and edge in self._seen_pub_cites:
                continue
            self._seen_pub_cites.add(edge)

            self._rel_pub_cites.writer.writerow(
                {
                    ":START_ID(PatentPublication)": pub_id,
                    ":END_ID(PatentPublication)": cited_id,
                    ":TYPE": "CITES",
                }
            )