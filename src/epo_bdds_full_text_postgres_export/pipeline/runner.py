from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from ..config import PostgresExportConfig
from ..extract.fulltext_extractor import FullTextExtractor
from ..io.postgres import PostgresFullTextRepository

XmlItem = Tuple[str, bytes]  # (source_id, xml_bytes)

class ProcessedXmlCheckpointStore:
    """
    Minimal placeholder. If you already have this in graph_export,
    just import/reuse it to avoid duplication.
    """
    def __init__(self, path: str) -> None:
        self._path = path
        self._seen: set[str] = set()
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    self._seen.add(line.strip())
        except FileNotFoundError:
            pass

    def has_processed(self, source_id: str) -> bool:
        return source_id in self._seen

    def mark_processed(self, source_id: str) -> None:
        if source_id in self._seen:
            return
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(source_id + "\n")
        self._seen.add(source_id)


@dataclass
class PostgresExportPipeline:
    config: PostgresExportConfig
    extractor: FullTextExtractor
    repo: PostgresFullTextRepository
    checkpoint: ProcessedXmlCheckpointStore

    def run(self, xml_items: Iterable[XmlItem]) -> None:
        self.config.validate()

        with self.repo.open() as conn:
            self.repo.ensure_schema(conn)

            n = 0
            for source_id, xml_bytes in xml_items:
                if self.checkpoint.has_processed(source_id):
                    continue

                # Store only whitelisted languages (claims are lang-scoped)
                for lang in self.config.language_whitelist:
                    rec = self.extractor.extract(source_id=source_id, xml_bytes=xml_bytes, lang=lang)
                    if rec is not None:
                        self.repo.upsert(conn, rec)

                self.checkpoint.mark_processed(source_id)

                n += 1
                if n % self.config.commit_every == 0:
                    conn.commit()

            conn.commit()