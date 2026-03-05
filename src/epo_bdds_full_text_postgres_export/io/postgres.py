from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from ..domain.models import FullTextRecord

_CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS patent_fulltext (
  source_id        TEXT NOT NULL,
  appln_id         TEXT NOT NULL,
  pub_id           TEXT NOT NULL,
  lang             TEXT NOT NULL,

  abstract_text    TEXT NULL,
  description_text TEXT NULL,
  claims_text      TEXT NULL,
  claims_json      JSONB NULL,

  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (pub_id, lang)
);

CREATE INDEX IF NOT EXISTS idx_patent_fulltext_source_id ON patent_fulltext(source_id);
"""

_UPSERT_SQL = """
INSERT INTO patent_fulltext (
  source_id, 
  appln_id, 
  pub_id, 
  lang,
  abstract_text, 
  description_text, 
  claims_text, 
  claims_json,
  updated_at
) VALUES (
  %(source_id)s, 
  %(appln_id)s, 
  %(pub_id)s, 
  %(lang)s,
  %(abstract_text)s, 
  %(description_text)s, 
  %(claims_text)s, 
  %(claims_json)s,
  now()
)
ON CONFLICT (pub_id, lang) 
DO UPDATE SET
  source_id = EXCLUDED.source_id,
  abstract_text = EXCLUDED.abstract_text,
  description_text = EXCLUDED.description_text,
  claims_text = EXCLUDED.claims_text,
  claims_json = EXCLUDED.claims_json,
  updated_at = now();
"""


@dataclass(frozen=True)
class PostgresConnectionFactory:
    """
    Creates psycopg connections.
    """
    dsn: str

    def connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self.dsn, row_factory=dict_row)
        # No timeout while bulk-loading huge BDDS archives
        conn.execute("SET statement_timeout = '0';")
        return conn


class PostgresFullTextRepository:
    """
    Repository responsible only for PostgreSQL persistence of FullTextRecord.
    """
    def __init__(self, connection_factory: PostgresConnectionFactory) -> None:
        self._connection_factory = connection_factory
        
    def open_connection(self) -> psycopg.Connection:
        return self._connection_factory.connect()
        
    def ensure_schema(self, conn: psycopg.Connection) -> None:
        conn.execute(_CREATE_SCHEMA_SQL)
        conn.commit()

    def upsert_record(self, conn: psycopg.Connection, record: FullTextRecord) -> None:
        conn.execute(
            _UPSERT_SQL,
            {
                "source_id": record.source_id,
                "appln_id": record.appln_id,
                "pub_id": record.pub_id,
                "lang": record.lang,
                "abstract_text": record.abstract_text,
                "description_text": record.description_text,
                "claims_text": record.claims_text,
                "claims_json": Json(record.claims_json) if record.claims_json is not None else None,
            },
        )