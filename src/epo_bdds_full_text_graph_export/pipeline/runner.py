from __future__ import annotations

from dataclasses import dataclass
import traceback
from typing import Iterable, Protocol, Tuple
import xml.etree.ElementTree as ET

from ..config import ExportConfig
from ..io.checkpoint_store import ProcessedXmlCheckpointStore
from ..io.csv_sink import CsvAppendSink
from ..extract.publication_extractor import PublicationExtractor
from ..extract.application_extractor import ApplicationExtractor
from ..extract.ipc_classification_extractor import IpcClassificationExtractor
from ..extract.cpc_classification_extractor import CpcClassificationExtractor
from ..extract.applicants_extractor import ApplicantExtractor
from ..extract.inventors_extractor import InventorExtractor
from ..extract.attorney_representative_extractor import AttorneyRepresentativeExtractor
from ..extract.citation_extractor import CitationExtractor
from ..graph.relationship_builder import RelationshipBuilder


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
    ipc_classifications_sink: RowSink
    cpc_classifications_sink: RowSink
    applicants_sink: RowSink
    inventors_sink: RowSink
    attorney_representatives_sink: RowSink
    citations_sink: RowSink
    relationships_sink: RowSink
    source_files_sink: RowSink

    publication_extractor: PublicationExtractor
    application_extractor: ApplicationExtractor
    ipc_classification_extractor: IpcClassificationExtractor
    cpc_classification_extractor: CpcClassificationExtractor
    applicant_extractor: ApplicantExtractor
    inventor_extractor: InventorExtractor
    attorney_representative_extractor: AttorneyRepresentativeExtractor
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
                    
                    relationship_builder = RelationshipBuilder()

                    publication_rows = self.publication_extractor.extract_publication_info(xml_root, source_id)
                    application_rows = self.application_extractor.extract_application_info(xml_root, source_id)
                    ipc_classification_rows = self.ipc_classification_extractor.extract_ipc_classifications(xml_root, source_id)
                    cpc_classification_rows = self.cpc_classification_extractor.extract_cpc_classifications(xml_root, source_id)
                    applicants_rows = self.applicant_extractor.extract_applicants(xml_root, source_id)
                    inventors_rows = self.inventor_extractor.extract_inventors(xml_root, source_id)
                    attorney_rows = self.attorney_representative_extractor.extract_attorney_representative(xml_root, source_id)
                    citation_rows = self.citation_extractor.extract_citations(xml_root, source_id)

                    

                    relationship_builder.ingest_publications(publication_rows)
                    relationship_builder.ingest_applications(application_rows)
                    relationship_builder.build_static_links()

                    relationship_builder.ingest_ipc(ipc_classification_rows)
                    relationship_builder.ingest_cpc(cpc_classification_rows)

                    applicants_rows = relationship_builder.enricher().enrich_applicants(applicants_rows)
                    inventors_rows = relationship_builder.enricher().enrich_inventors(inventors_rows)
                    attorney_rows = relationship_builder.enricher().enrich_attorneys(attorney_rows)

                    relationship_builder.ingest_applicants(applicants_rows)
                    relationship_builder.ingest_inventors(inventors_rows)
                    relationship_builder.ingest_attorneys(attorney_rows)

                    relationship_rows = [r.as_dict() for r in relationship_builder.relationship_rows()]
                    source_files_rows = relationship_builder.source_file_rows()
                    
                    self.publications_sink.write_rows(publication_rows)
                    self.applications_sink.write_rows(application_rows)
                    self.ipc_classifications_sink.write_rows(ipc_classification_rows)
                    self.cpc_classifications_sink.write_rows(cpc_classification_rows)
                    self.applicants_sink.write_rows(applicants_rows)
                    self.inventors_sink.write_rows(inventors_rows)
                    self.attorney_representatives_sink.write_rows(attorney_rows)
                    self.citations_sink.write_rows(citation_rows)
                    self.source_files_sink.write_rows(source_files_rows)
                    self.relationships_sink.write_rows(relationship_rows)

                    self.checkpoint_store.mark_done(conn, source_id)
                    conn.commit()

                    processed += 1
                    if self.stop_after is not None and processed >= self.stop_after:
                        break

                except Exception:
                    error_details = traceback.format_exc()

                    self.checkpoint_store.record_failure_safely(
                        conn,
                        source_id,
                        error_details,
                        context=f"xml_item={source_id}",
                    )

                    conn.commit()

                    print(f"[FAILED] {source_id}")
                    print(error_details)

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
    ipc_classifications_sink = CsvAppendSink(config.tables.ipc_classifications_csv, config.schemas.ipc_classifications_fields)
    cpc_classifications_sink = CsvAppendSink(config.tables.cpc_classifications_csv, config.schemas.cpc_classifications_fields)
    applicants_sink = CsvAppendSink(config.tables.applicants_csv, config.schemas.applicants_fields)
    inventors_sink = CsvAppendSink(config.tables.inventors_csv, config.schemas.inventors_fields)
    attorney_representatives_sink = CsvAppendSink(config.tables.attorney_representatives_csv, config.schemas.attorney_representatives_fields)
    citations_sink = CsvAppendSink(config.tables.citations_csv, config.schemas.citations_fields)
    relationships_sink = CsvAppendSink(config.tables.relationships_csv, config.schemas.relationships_fields)
    source_files_sink = CsvAppendSink(config.tables.source_files_csv, config.schemas.source_files_fields)

    return GraphExportPipeline(
        checkpoint_store=checkpoint_store,
        publications_sink=publications_sink,
        applications_sink=applications_sink,
        ipc_classifications_sink=ipc_classifications_sink,
        cpc_classifications_sink=cpc_classifications_sink,
        applicants_sink=applicants_sink,
        inventors_sink=inventors_sink,
        attorney_representatives_sink=attorney_representatives_sink,
        citations_sink=citations_sink,
        relationships_sink=relationships_sink,
        source_files_sink=source_files_sink,
        publication_extractor=PublicationExtractor(),
        application_extractor=ApplicationExtractor(),
        ipc_classification_extractor=IpcClassificationExtractor(),
        cpc_classification_extractor=CpcClassificationExtractor(),
        applicant_extractor=ApplicantExtractor(),
        inventor_extractor=InventorExtractor(),
        attorney_representative_extractor=AttorneyRepresentativeExtractor(),
        citation_extractor=CitationExtractor(),
        stop_after=config.stop_after,
        fail_fast=config.fail_fast,
    )