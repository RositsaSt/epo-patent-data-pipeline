from __future__ import annotations

import io
import zipfile

import pytest


@pytest.fixture
def make_zip():
    """
    Factory fixture: returns a callable that builds an in-memory ZIP as bytes.

    Usage:
        data = make_zip({"ep001.xml": b"<patent/>", "readme.txt": b"hello"})
    """
    def _make(members: dict[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, content in members.items():
                zf.writestr(name, content)
        buf.seek(0)
        return buf.read()

    return _make
