from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class CsvAppendSink:
    path: Path
    fieldnames: Sequence[str]

    def write_rows(self, rows: Iterable[Mapping[str, object]]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self.path.exists()

        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()

            n = 0
            for row in rows:
                writer.writerow({k: self._to_str(v) for k, v in row.items()})
                n += 1
            return n

    @staticmethod
    def _to_str(v: object) -> str:
        return "" if v is None else str(v)