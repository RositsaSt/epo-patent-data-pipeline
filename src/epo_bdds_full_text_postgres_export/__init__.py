"""
Parse EPO BDDS full-text XMLs and upsert extracted sections (abstract/description/claims)
into a PostgreSQL table.

This package intentionally keeps:
- domain models (pure data)
- extractors (pure parsing, no IO)
- repositories (DB IO only)
- pipeline (orchestration)
- CLI (wiring)
"""