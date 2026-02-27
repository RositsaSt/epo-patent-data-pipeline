from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class CsvAppendSink:
    """
    Append-only CSV writer.

    - Creates parent dirs automatically.
    - Writes header exactly once (if file is new or empty).
    - Ignores extra keys in rows (extrasaction="ignore").
    """
    csv_path: Path
    fieldnames: Sequence[str]

    def write_rows(self, rows: Iterable[Mapping[str, object]]) -> int:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        rows_written = 0
        should_write_header = (not self.csv_path.exists()) or self.csv_path.stat().st_size == 0
        
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames, extrasaction="ignore")
            
            if should_write_header:
                writer.writeheader()
                
            for row in rows:
                writer.writerow({key: _stringify(row.get(key)) for key in self.fieldnames})
                rows_written += 1
        
        return rows_written
    
def _stringify(value: object) -> str:
    """Convert a value to a CSV-safe string (None -> empty)."""
    if value is None:
        return ""
    return str(value)