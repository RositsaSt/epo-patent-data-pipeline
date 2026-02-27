from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Tuple
import xml.etree.ElementTree as ET

from ..config import ExportConfig
from ..io.checkpoint_store import ProcessedXmlCheckpointStore
from ..io.csv_sink import CsvAppendSink
from ..extract.publication_extractor import PublicationExtractor
from ..extract.application_extractor import ApplicationExtractor
from ..extract.person_extractor import PersonExtractor
from ..extract.citation_extractor import CitationExtractor


XmlItem = Tuple[str, bytes]  # (source_id, xml_bytes)


class RowSink(Protocol):
    def write_rows(self, rows: Iterable[dict]) -> int:
        """
        Write rows to the sink.

        Returns the number of rows written.
        """
        ...


class XmlCheckpoint(Protocol):
    def open_connection(self): ...
    def is_done(self, conn, source_id: str) -> bool: ...
    def mark_done(self, conn, source_id: str) -> None: ...
    def mark_failed(self, conn, source_id: str, error: str) -> None: ...


@dataclass(frozen=True)
class GraphExportPipeline:
    """
    Orchestrates:
      XML bytes -> XML root -> extracted rows -> CSV sinks + checkpoint updates
    """
    checkpoint_store: ProcessedXmlCheckpointStore

    publications_sink: RowSink
    applications_sink: RowSink
    persons_sink: RowSink
    citations_sink: RowSink
    relationships_sink: RowSink

    publication_extractor: PublicationExtractor
    application_extractor: ApplicationExtractor
    person_extractor: PersonExtractor
    citation_extractor: CitationExtractor

    stop_after: int | None = None
    fail_fast: bool = False

    def run(self, xml_items: Iterable[XmlItem]) -> None:
        conn = self.checkpoint_store.open_connection()
        processed = 0

        try:
            for source_id, xml_bytes in xml_items:
                if self.checkpoint_store.is_done(conn, source_id):
                    continue

                try:
                    xml_root = ET.fromstring(xml_bytes)

                    publication_rows = self.publication_extractor.extract(xml_root, source_id)
                    application_rows = self.application_extractor.extract(xml_root, source_id)
                    person_rows = self.person_extractor.extract(xml_root, source_id)
                    citation_rows = self.citation_extractor.extract(xml_root, source_id)

                    relationship_rows: list[dict] = []  # TODO: implement relationship builder

                    self.publications_sink.write_rows(publication_rows)
                    self.applications_sink.write_rows(application_rows)
                    self.persons_sink.write_rows(person_rows)
                    self.citations_sink.write_rows(citation_rows)
                    self.relationships_sink.write_rows(relationship_rows)

                    self.checkpoint_store.mark_done(conn, source_id)
                    conn.commit()

                    processed += 1
                    if self.stop_after is not None and processed >= self.stop_after:
                        break

                except Exception as exc:
                    self.checkpoint_store.mark_failed(conn, source_id, repr(exc))
                    conn.commit()
                    if self.fail_fast:
                        raise

        finally:
            conn.close()


def build_pipeline(config: ExportConfig) -> GraphExportPipeline:
    """
    Factory that wires concrete sinks/extractors/checkpoint store into a pipeline.
    """
    checkpoint_store = ProcessedXmlCheckpointStore(config.checkpoint_db)

    publications_sink = CsvAppendSink(config.tables.publications_csv, config.schemas.publications_fields)
    applications_sink = CsvAppendSink(config.tables.applications_csv, config.schemas.applications_fields)
    persons_sink = CsvAppendSink(config.tables.persons_csv, config.schemas.persons_fields)
    citations_sink = CsvAppendSink(config.tables.citations_csv, config.schemas.citations_fields)
    relationships_sink = CsvAppendSink(config.tables.relationships_csv, config.schemas.relationships_fields)

    return GraphExportPipeline(
        checkpoint_store=checkpoint_store,
        publications_sink=publications_sink,
        applications_sink=applications_sink,
        persons_sink=persons_sink,
        citations_sink=citations_sink,
        relationships_sink=relationships_sink,
        publication_extractor=PublicationExtractor(),
        application_extractor=ApplicationExtractor(),
        person_extractor=PersonExtractor(),
        citation_extractor=CitationExtractor(),
        stop_after=config.stop_after,
        fail_fast=config.fail_fast,
    )