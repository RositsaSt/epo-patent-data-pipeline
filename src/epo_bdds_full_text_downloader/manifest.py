from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Iterable, Mapping, Optional, TypedDict


# =============================================================================
# PUBLIC TYPES
# =============================================================================
class ManifestStatus(str, Enum):
    """Pipeline state for a single filename."""
    DOWNLOADED = "downloaded"
    CLEANED = "cleaned"
    MOVED = "moved"
    EMPTY = "empty"
    FAILED = "failed"
    SKIPPED = "skipped"


class ManifestRow(TypedDict):
    """One row in the manifest CSV."""
    filename: str
    status: str          # stored as string for CSV compatibility
    timestamp: str              # unix timestamp (seconds)
    raw_size: str
    filtered_size: str
    final_size: str
    message: str


COLUMNS: tuple[str, ...] = (
    "filename",
    "status",
    "timestamp",
    "raw_size",
    "filtered_size",
    "final_size",
    "message",
)


# =============================================================================
# IMPLEMENTATION
# =============================================================================

@dataclass(frozen=True)
class CsvManifest:
    """
    CSV-backed manifest for resumable ingest pipelines.

    This class keeps a single `latest` row per filename (upsert semantics).
    Implementation is intentionally simple:
      - Read all rows -> dict keyed by filename
      - Upsert -> atomic rewrite to disk

    Safety:
      - Uses atomic replace (write to .tmp then os.replace) to avoid corrupt files.
    """
    path: Path
    now: Callable[[], int] = lambda: int(time.time())

    def read_all(self) -> Dict[str, ManifestRow]:
        """
        Load the manifest into a dict keyed by filename.

        Returns:
            dict: filename -> ManifestRow
        """
        if not self.path.exists():
            return {}

        rows: Dict[str, ManifestRow] = {}
        with self.path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Ignore malformed rows safely (optional: raise instead)
                filename = (row.get("filename") or "").strip()
                if not filename:
                    continue

                # Ensure all columns exist so downstream code can rely on keys
                normalized: ManifestRow = {
                    "filename": filename,
                    "status": (row.get("status") or "").strip(),
                    "timestamp": (row.get("timestamp") or "").strip(),
                    "raw_size": (row.get("raw_size") or "").strip(),
                    "filtered_size": (row.get("filtered_size") or "").strip(),
                    "final_size": (row.get("final_size") or "").strip(),
                    "message": (row.get("message") or "").strip(),
                }
                rows[filename] = normalized

        return rows

    def upsert(self, record: ManifestRow) -> None:
        """
        Insert or update a row by filename and persist to disk.

        Notes:
            This rewrites the whole file (simple and robust for moderate sizes).
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        all_rows = self.read_all()
        all_rows[record["filename"]] = record

        self._atomic_write(all_rows.values())

    def mark(
        self,
        filename: str,
        status: ManifestStatus,
        *,
        raw_size: str = "",
        filtered_size: str = "",
        final_size: str = "",
        message: str = "",
    ) -> None:
        """
        Convenience wrapper to update a filename's status.

        Args:
            filename: The archive filename (key).
            status: Pipeline stage/status (Enum).
            raw_size: Raw download size in bytes (string to keep CSV stable).
            filtered_size: Filtered staging size in bytes.
            final_size: Final moved artifact size in bytes.
            message: Free-form note for debugging/auditing.
        """
        record: ManifestRow = {
            "filename": filename,
            "status": status.value,
            "timestamp": str(self.now()),
            "raw_size": raw_size,
            "filtered_size": filtered_size,
            "final_size": final_size,
            "message": message,
        }
        self.upsert(record)

    # =============================================================================
    # Internals
    # =============================================================================


    def _atomic_write(self, rows: Iterable[ManifestRow]) -> None:
        """
        Atomically rewrite the manifest to `self.path`.

        Implementation:
            write to `<path>.tmp` then `os.replace(tmp, path)` (atomic on POSIX).
        """
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")

        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()

            # Stable order makes diffs nicer and easier for debugging
            for row in sorted(rows, key=lambda r: r["filename"]):
                writer.writerow({col: row.get(col, "") for col in COLUMNS})

            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, self.path)
