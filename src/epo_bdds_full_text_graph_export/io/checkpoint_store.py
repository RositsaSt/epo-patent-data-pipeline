# from __future__ import annotations

# import sqlite3
# from dataclasses import dataclass
# from pathlib import Path


# @dataclass(frozen=True)
# class ProcessedXmlCheckpointStore:
#     """
#     SQLite-backed checkpoint store.

#     Tracks each processed XML by a stable source_id and status:
#     - done
#     - failed (+ error message)

#     WAL + NORMAL sync is a good tradeoff for long-running pipelines.
#     """
#     db_path: Path

#     def open_connection(self) -> sqlite3.Connection:
#         self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
#         conn = sqlite3.connect(self.db_path)
#         conn.execute("PRAGMA journal_mode=WAL;")
#         conn.execute("PRAGMA synchronous=NORMAL;")
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS processed_xml (
#                 source_id  TEXT PRIMARY KEY,
#                 status     TEXT NOT NULL,
#                 error      TEXT,
#                 updated_at TEXT NOT NULL DEFAULT (datetime('now'))
#             );
#         """)

#         return conn
    
#     def is_done(self,conn: sqlite3.Connection, source_id: str) -> bool:
#         row = conn.execute(
#             "SELECT status FROM processed_xml WHERE source_id = ? AND status = 'done' LIMIT 1",
#             (source_id,),
#         ).fetchone()
        
#         return row is not None
    
#     def mark_done(self, conn: sqlite3.Connection, source_id: str) -> None:
#         conn.execute(
#             """
#             INSERT INTO processed_xml (source_id, status, error)
#             VALUES (?, 'done', NULL) 
#             ON CONFLICT(source_id) DO UPDATE SET 
#                 status='done', 
#                 error=NULL, 
#                 updated_at=datetime('now')
#             """, 
#             (source_id,),
#         )
    
#     def mark_failed(self, conn: sqlite3.Connection, source_id: str, error: str) -> None:
#         conn.execute(
#             """
#             INSERT INTO processed_xml (source_id, status, error)
#             VALUES (?, 'failed', ?) 
#             ON CONFLICT(source_id) DO UPDATE SET 
#                 status='failed', 
#                 error=excluded.error, 
#                 updated_at=datetime('now')
#             """, 
#             (source_id, error[:2000]),
#         )

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProcessedXmlCheckpointStore:
    """
    SQLite-backed checkpoint store.

    Tracks each processed XML by a stable source_id and status:
      - done
      - failed (+ error message)

    Improvements:
      - validates source_id so it can’t be None/blank
      - makes mark_failed resilient if error is None (prevents the exact TypeError you saw)
      - optional: stores a short "context" note to help pinpoint where/why something failed
      - provides a helper to wrap an exception into a good error string
      - provides a helper to record failure safely without crashing your pipeline
    """
    db_path: Path

    def open_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_xml (
                source_id   TEXT PRIMARY KEY,
                status      TEXT NOT NULL,
                error       TEXT,
                context     TEXT,
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        return conn

    # -------------------------
    # Validation / normalization
    # -------------------------
    @staticmethod
    def _norm_source_id(source_id: object) -> str:
        """
        Ensure source_id is a non-empty string.
        This turns silent None propagation into a clear error early.
        """
        if source_id is None:
            raise ValueError("source_id is None (expected a non-empty string)")
        sid = str(source_id).strip()
        if not sid:
            raise ValueError("source_id is empty/blank (expected a non-empty string)")
        return sid

    @staticmethod
    def _norm_error(error: object, limit: int = 2000) -> str:
        """
        Ensure error is always a string, never None.
        This specifically prevents: TypeError("'NoneType' object is not subscriptable")
        from error[:2000] when error=None.
        """
        if error is None:
            return ""
        return str(error)[:limit]

    @staticmethod
    def _norm_context(context: object, limit: int = 2000) -> Optional[str]:
        """
        Optional extra info about where the failure happened.
        Keep it short; SQLite TEXT can hold more, but this avoids bloat.
        """
        if context is None:
            return None
        ctx = str(context).strip()
        if not ctx:
            return None
        return ctx[:limit]

    # -------------------------
    # Public API
    # -------------------------
    def is_done(self, conn: sqlite3.Connection, source_id: str) -> bool:
        sid = self._norm_source_id(source_id)
        row = conn.execute(
            "SELECT 1 FROM processed_xml WHERE source_id = ? AND status = 'done' LIMIT 1",
            (sid,),
        ).fetchone()
        return row is not None

    def mark_done(self, conn: sqlite3.Connection, source_id: str) -> None:
        sid = self._norm_source_id(source_id)
        conn.execute(
            """
            INSERT INTO processed_xml (source_id, status, error, context)
            VALUES (?, 'done', NULL, NULL)
            ON CONFLICT(source_id) DO UPDATE SET
                status='done',
                error=NULL,
                context=NULL,
                updated_at=datetime('now')
            """,
            (sid,),
        )

    def mark_failed(
        self,
        conn: sqlite3.Connection,
        source_id: str,
        error: object,
        *,
        context: object = None,
    ) -> None:
        sid = self._norm_source_id(source_id)
        err = self._norm_error(error)
        ctx = self._norm_context(context)

        conn.execute(
            """
            INSERT INTO processed_xml (source_id, status, error, context)
            VALUES (?, 'failed', ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                status='failed',
                error=excluded.error,
                context=excluded.context,
                updated_at=datetime('now')
            """,
            (sid, err, ctx),
        )

    # -------------------------
    # Convenience helpers for better failure logging
    # -------------------------
    def record_failure_safely(
        self,
        conn: sqlite3.Connection,
        source_id: object,
        error: object,
        *,
        context: object = None,
    ) -> None:
        """
        Best-effort failure recording that will not crash your pipeline,
        even if source_id is broken.

        If source_id is invalid, we still try to store something usable by
        synthesizing a fallback id.
        """
        try:
            sid = self._norm_source_id(source_id)
        except Exception as sid_exc:
            # If your pipeline can't compute a good source_id, we still keep a breadcrumb.
            sid = f"__invalid_source_id__:{self._norm_error(sid_exc, 300)}"

        try:
            self.mark_failed(conn, sid, error, context=context)
        except Exception as write_exc:
            # Absolute last resort: avoid raising; print something deterministic.
            # If you have logging, replace this print with logger.exception(...)
            print(
                "Checkpoint write failed:",
                {"source_id": sid, "write_exc": str(write_exc), "original_error": str(error)},
            )

    @staticmethod
    def exception_to_error_string(exc: BaseException) -> str:
        """
        Turn an exception into a concise error string.
        (If you prefer full tracebacks, use traceback.format_exc() at call site.)
        """
        return f"{exc.__class__.__name__}: {exc}"