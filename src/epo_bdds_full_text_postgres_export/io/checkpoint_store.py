from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Set


class CheckpointStore(Protocol):
    """
    Protocol for persisting which XML source_ids have already been processed.
    """

    def has_processed(self, source_id: str) -> bool: ...
    def mark_processed(self, source_id: str) -> None: ...


@dataclass
class TextFileCheckpointStore:
    """
    Simple checkpoint store backed by a newline-delimited text file.

    Each line: source_id
    """

    checkpoint_path: Path

    def __post_init__(self) -> None:
        self._seen: Set[str] = set()
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        if self.checkpoint_path.exists():
            for line in self.checkpoint_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self._seen.add(line)

    def has_processed(self, source_id: str) -> bool:
        return source_id in self._seen

    def mark_processed(self, source_id: str) -> None:
        if source_id in self._seen:
            return
        with self.checkpoint_path.open("a", encoding="utf-8") as f:
            f.write(source_id + "\n")
        self._seen.add(source_id)