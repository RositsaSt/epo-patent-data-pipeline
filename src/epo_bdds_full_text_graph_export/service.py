from __future__ import annotations

"""
Graph export orchestrator.
"""

from typing import Optional

from .neo4j_csv_writer import Neo4jCsvGraphWriter
from .xml_parser import XmlPatentDocumentParser
from .xml_source import NestedArchiveXmlSource


class GraphExportService:
    """
    Coordinate XML discovery, parsing, and CSV writing.

    Single responsibility:
        - Wire together the three lower‑level components to execute a full
          export run, respecting a document limit when requested.
    """

    def __init__(
        self,
        xml_source: NestedArchiveXmlSource,
        xml_parser: XmlPatentDocumentParser,
        graph_writer: Neo4jCsvGraphWriter,
        document_limit: Optional[int] = None,
    ) -> None:
        self._xml_source = xml_source
        self._xml_parser = xml_parser
        self._graph_writer = graph_writer
        self._document_limit = document_limit

    def run(self) -> int:
        """
        Run the export until input is exhausted or the limit is reached.

        Returns:
            The number of successfully processed XML documents.
        """
        processed_documents = 0

        try:
            for source_id, xml_bytes in self._xml_source.iter_xml_documents():
                if self._document_limit is not None and processed_documents >= self._document_limit:
                    break

                parsed_document = self._xml_parser.parse(source_id, xml_bytes)
                if parsed_document is None:
                    continue

                self._graph_writer.write_document(parsed_document)
                processed_documents += 1

        finally:
            self._graph_writer.close()

        return processed_documents

