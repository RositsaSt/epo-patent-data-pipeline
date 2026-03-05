from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from ..domain.models import FullTextRecord

DDL = """
CREATE TABLE IF NOT EXISTS patent_fulltext (
  source_id        TEXT NOT NULL,
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

UPSERT = """
INSERT INTO patent_fulltext (
  source_id, pub_id, lang,
  abstract_text, description_text, claims_text, claims_json,
  updated_at
) VALUES (
  %(source_id)s, %(pub_id)s, %(lang)s,
  %(abstract_text)s, %(description_text)s, %(claims_text)s, %(claims_json)s,
  now()
)
ON CONFLICT (pub_id, lang) DO UPDATE SET
  source_id = EXCLUDED.source_id,
  abstract_text = EXCLUDED.abstract_text,
  description_text = EXCLUDED.description_text,
  claims_text = EXCLUDED.claims_text,
  claims_json = EXCLUDED.claims_json,
  updated_at = now();
"""

class PostgresFullTextRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def open(self) -> psycopg.Connection:
        conn = psycopg.connect(self._dsn, row_factory=dict_row)
        conn.execute("SET statement_timeout = '0';")
        return conn

    def ensure_schema(self, conn: psycopg.Connection) -> None:
        conn.execute(DDL)
        conn.commit()

    def upsert(self, conn: psycopg.Connection, rec: FullTextRecord) -> None:
        conn.execute(
            UPSERT,
            {
                "source_id": rec.source_id,
                "pub_id": rec.pub_id,
                "lang": rec.lang,
                "abstract_text": rec.abstract_text,
                "description_text": rec.description_text,
                "claims_text": rec.claims_text,
                "claims_json": Json(rec.claims_json) if rec.claims_json is not None else None,
            },
        )