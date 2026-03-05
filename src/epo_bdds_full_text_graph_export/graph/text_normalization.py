from __future__ import annotations

from typing import Optional


def normalize_text(value: Optional[str]) -> str:
    """Return a stripped string; None becomes empty string."""
    return (value or "").strip()


def normalize_lower(value: Optional[str]) -> str:
    """Return a lowercase, stripped string; None becomes empty string."""
    return normalize_text(value).lower()