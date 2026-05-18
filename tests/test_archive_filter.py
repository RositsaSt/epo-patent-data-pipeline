from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from epo_bdds_full_text_downloader.archive_filter import (
    ArchiveFilterOptions,
    ArchiveFilterRules,
    filter_archive_bytes,
    filter_archive_file,
    should_keep_xml,
    validate_zip_crc,
)

_RULES = ArchiveFilterRules(xml_basename_prefix="ep")
_OPTS = ArchiveFilterOptions(strict=True)


# ---------------------------------------------------------------------------
# should_keep_xml
# ---------------------------------------------------------------------------

def test_keep_matching_xml():
    assert should_keep_xml("DOC/ep12345.xml", _RULES) is True


def test_drop_non_matching_xml():
    assert should_keep_xml("DOC/us12345.xml", _RULES) is False


def test_keep_all_xml_when_prefix_empty():
    rules = ArchiveFilterRules(xml_basename_prefix="")
    assert should_keep_xml("us999.xml", rules) is True


def test_drop_non_xml_file():
    assert should_keep_xml("readme.txt", _RULES) is False


# ---------------------------------------------------------------------------
# filter_archive_bytes — ZIP
# ---------------------------------------------------------------------------

def test_filter_zip_keeps_matching_xmls(make_zip):
    data = make_zip({"ep001.xml": b"<p/>", "ep002.xml": b"<q/>"})
    result = filter_archive_bytes(data, "delivery.zip", _RULES, options=_OPTS)
    assert result
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert set(zf.namelist()) == {"ep001.xml", "ep002.xml"}


def test_filter_zip_drops_non_matching_xml(make_zip):
    data = make_zip({"us001.xml": b"<p/>", "ep002.xml": b"<q/>"})
    result = filter_archive_bytes(data, "delivery.zip", _RULES, options=_OPTS)
    assert result
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert zf.namelist() == ["ep002.xml"]


def test_filter_zip_drops_non_xml_files(make_zip):
    data = make_zip({"readme.txt": b"hello", "ep001.xml": b"<p/>"})
    result = filter_archive_bytes(data, "delivery.zip", _RULES, options=_OPTS)
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert "readme.txt" not in zf.namelist()


def test_filter_zip_returns_empty_when_nothing_matches(make_zip):
    data = make_zip({"us001.xml": b"<p/>", "readme.txt": b"hi"})
    result = filter_archive_bytes(data, "delivery.zip", _RULES, options=_OPTS)
    assert result == b""


def test_filter_zip_nested_zip_in_zip(make_zip):
    inner_zip = make_zip({"ep001.xml": b"<patent/>"})
    outer_zip = make_zip({"inner.zip": inner_zip})
    result = filter_archive_bytes(outer_zip, "outer.zip", _RULES, options=_OPTS)
    assert result  # nested XML was found
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert "inner.zip" in zf.namelist()


# ---------------------------------------------------------------------------
# validate_zip_crc
# ---------------------------------------------------------------------------

def test_validate_zip_crc_valid(make_zip, tmp_path):
    data = make_zip({"ep001.xml": b"<patent/>"})
    p = tmp_path / "test.zip"
    p.write_bytes(data)
    validate_zip_crc(p)  # must not raise


def test_validate_zip_crc_invalid_file(tmp_path):
    p = tmp_path / "bad.zip"
    p.write_bytes(b"this is not a zip")
    with pytest.raises(RuntimeError):
        validate_zip_crc(p)


# ---------------------------------------------------------------------------
# filter_archive_file
# ---------------------------------------------------------------------------

def test_filter_archive_file_writes_output(make_zip, tmp_path):
    src = tmp_path / "delivery.zip"
    dst = tmp_path / "filtered.zip"
    src.write_bytes(make_zip({"ep001.xml": b"<patent/>"}))

    kept = filter_archive_file(src, dst, _RULES, options=_OPTS)

    assert kept is True
    assert dst.exists()
    with zipfile.ZipFile(dst) as zf:
        assert "ep001.xml" in zf.namelist()


def test_filter_archive_file_returns_false_when_nothing_kept(make_zip, tmp_path):
    src = tmp_path / "delivery.zip"
    dst = tmp_path / "filtered.zip"
    src.write_bytes(make_zip({"us001.xml": b"<p/>"}))

    kept = filter_archive_file(src, dst, _RULES, options=_OPTS)

    assert kept is False
    assert not dst.exists()
