from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from ..config import PostgresExportConfig
from ..extract.fulltext_extractor import FullTextExtractor
from ..io.checkpoint_store import CheckpointStore
from ..io.postgres import PostgresFullTextRepository

XmlItem = Tuple[str, bytes]  # (source_id, xml_bytes)


@dataclass
class PostgresExportPipeline:
    """
    Orchestrates:
      - skipping already-processed XMLs via checkpoint store
      - extracting full-text content
      - upserting into PostgreSQL
      - checkpointing after successful processing
    """
    config: PostgresExportConfig
    extractor: FullTextExtractor
    repository: PostgresFullTextRepository
    checkpoint_store: CheckpointStore

    def run(self, xml_items: Iterable[XmlItem]) -> None:
        """
        Run the export pipeline over an iterable of (source_id, xml_bytes).
        """
        self.config.validate()

        with self.repository.open_connection() as conn:
            self.repository.ensure_schema(conn)

            processed_since_commit = 0
            
            for source_id, xml_bytes in xml_items:
                if self.checkpoint_store.has_processed(source_id):
                    continue
                
                self._process_single_xml(conn=conn, source_id=source_id, xml_bytes=xml_bytes)

                # Only mark processed if we got here without raising.
                self.checkpoint_store.mark_processed(source_id)
                
                processed_since_commit += 1
                if processed_since_commit >= self.config.commit_every:
                    conn.commit()
                    processed_since_commit = 0
                    
                conn.commit()
                
    def _process_single_xml(self, *, conn, source_id: str, xml_bytes: bytes) -> None:
        """
        Extract and upsert all configured languages for a single XML.
        """
        for lang in self.config.language_whitelist:
            record = self.extractor.extract_record(source_id=source_id, xml_bytes=xml_bytes, lang=lang)
            if record is None:
                continue
            self.repository.upsert_record(conn, record)
