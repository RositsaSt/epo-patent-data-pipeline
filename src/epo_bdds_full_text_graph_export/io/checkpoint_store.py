from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessedXmlCheckpointStore:
    """
    SQLite-backed checkpoint store.

    Tracks each processed XML by a stable source_id and status:
    - done
    - failed (+ error message)

    WAL + NORMAL sync is a good tradeoff for long-running pipelines.
    """
    db_path: Path

    def open_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_xml (
                source_id  TEXT PRIMARY KEY,
                status     TEXT NOT NULL,
                error      TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        return conn
    
    def is_done(self,conn: sqlite3.Connection, source_id: str) -> bool:
        row = conn.execute(
            "SELECT status FROM processed_xml WHERE source_id = ? AND status = 'done' LIMIT 1",
            (source_id,),
        ).fetchone()
        
        return row is not None
    
    def mark_done(self, conn: sqlite3.Connection, source_id: str) -> None:
        conn.execute(
            """
            INSERT INTO processed_xml (source_id, status, error)
            VALUES (?, 'done', NULL) 
            ON CONFLICT(source_id) DO UPDATE SET 
                status='done', 
                error=NULL, 
                updated_at=datetime('now')
            """, 
            (source_id,),
        )
    
    def mark_failed(self, conn: sqlite3.Connection, source_id: str, error: str) -> None:
        conn.execute(
            """
            INSERT INTO processed_xml (source_id, status, error)
            VALUES (?, 'failed', ?) 
            ON CONFLICT(source_id) DO UPDATE SET 
                status='failed', 
                error=excluded.error, 
                updated_at=datetime('now')
            """, 
            (source_id, error[:2000]),
        )