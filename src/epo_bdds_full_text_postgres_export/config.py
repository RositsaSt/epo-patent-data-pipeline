from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class PostgresExportConfig:
    """
    Configuration for exporting EPO BDDS full-text content into PostgreSQL.
    """
    postgres_dsn: str

    # Keep only English by default
    language_whitelist: tuple[str, ...] = ("en",)

    # Batch commits for speed
    commit_every: int = 200

    def validate(self) -> None:
        """
        Validate config values and raise ValueError on invalid configuration.
        """
        if not self.postgres_dsn.strip():
            raise ValueError("postgres_dsn is empty. Set PATENTS_PG_DSN (e.g. postgresql://user:pass@host:5432/db).")
        
        if self.commit_every <= 0:
            raise ValueError("commit_every must be a positive integer.")
        
        if not self.language_whitelist:
            raise ValueError("language_whitelist must contain at least one language code.")