from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple
import xml.etree.ElementTree as ET

from ..config import ExportConfig
from ..io.checkpoint_store import CheckpointStore
from ..io.csv_sink import CsvAppendSink
from ..extract.publication_extractor import PublicationExtractor
from ..extract.application_extractor import ApplicationExtractor
from ..extract.person_extractor import PersonExtractor
from ..extract.citation_extractor import CitationExtractor


@dataclass(frozen=True)
class GraphExportPipeline:
    checkpoint_store: CheckpointStore

    publications_sink: CsvAppendSink
    applications_sink: CsvAppendSink
    persons_sink: CsvAppendSink
    citations_sink: CsvAppendSink
    relationships_sink: CsvAppendSink

    publication_extractor: PublicationExtractor
    application_extractor: ApplicationExtractor
    person_extractor: PersonExtractor
    citation_extractor: CitationExtractor

    stop_after: int | None = None
    fail_fast: bool = False

    def run(self, xml_items: Iterable[Tuple[str, bytes]]) -> None:
        conn = self.checkpoint_store.open()
        processed = 0

        try:
            for source_id, xml_bytes in xml_items:
                if self.checkpoint_store.is_done(conn, source_id):
                    continue

                try:
                    root = ET.fromstring(xml_bytes)

                    publication_rows = self.publication_extractor.extract(root, source_id)
                    application_rows = self.application_extractor.extract(root, source_id)
                    person_rows = self.person_extractor.extract(root, source_id)
                    citation_rows = self.citation_extractor.extract(root, source_id)

                    # TODO: build relationships rows (pub->app, app->person, pub->pub cites, etc.)
                    relationship_rows: list[dict] = []

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
    checkpoint_store = CheckpointStore(config.checkpoint_db)

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