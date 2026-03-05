from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class PostgresExportConfig:
    # Example: "postgresql://user:pass@localhost:5432/patents"
    pg_dsn: str = os.getenv("PATENTS_PG_DSN", "")

    # Keep only English by default (you can widen later)
    language_whitelist: tuple[str, ...] = ("en",)

    # Batch commits for speed
    commit_every: int = int(os.getenv("PATENTS_PG_COMMIT_EVERY", "200"))

    def validate(self) -> None:
        if not self.pg_dsn:
            raise SystemExit("Missing PATENTS_PG_DSN env var (e.g. postgresql://user:pass@host:5432/db).")