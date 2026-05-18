from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Neo4jLoaderConfig:
    uri: str
    user: str
    password: str
    csv_dir: Path
    batch_size: int = 500
    checkpoint_db: Path = Path("data/checkpoints/neo4j_loader_checkpoint.sqlite")
