from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from download import (
    cache_path_for,
    download_pdf,
    cache_hit,
    CACHE_DIR,
)


def test_cache_path_pattern():
    p = cache_path_for(stadt="Bochum", typ="gmb", jahr=2025)
    assert p.name == "bochum-gmb-2025.pdf"
    assert p.parent == CACHE_DIR


def test_cache_hit_when_file_exists_and_notion_stand_older(tmp_path):
    cache_file = tmp_path / "test.pdf"
    cache_file.write_bytes(b"%PDF-1.4 minimal")
    # Notion-Stand-Datum aelter als Cache-Mtime → Cache valide
    assert cache_hit(cache_file, notion_stand_iso="2024-01-01") is True


def test_cache_miss_when_notion_stand_newer(tmp_path):
    cache_file = tmp_path / "test.pdf"
    cache_file.write_bytes(b"%PDF-1.4 minimal")
    # Notion-Stand-Datum in der Zukunft → Cache invalide
    assert cache_hit(cache_file, notion_stand_iso="2030-12-31") is False


def test_cache_miss_when_file_missing(tmp_path):
    cache_file = tmp_path / "nope.pdf"
    assert cache_hit(cache_file, notion_stand_iso=None) is False


def test_download_pdf_writes_file(tmp_path):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b"%PDF-1.4 fake content"
    fake_response.headers = {"Content-Length": "20"}
    target = tmp_path / "downloaded.pdf"
    with patch("download.requests.get", return_value=fake_response):
        download_pdf("https://bochum.de/test.pdf", target)
    assert target.exists()
    assert target.read_bytes() == b"%PDF-1.4 fake content"


def test_download_pdf_rejects_too_large(tmp_path):
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.headers = {"Content-Length": str(60 * 1024 * 1024)}  # 60 MB
    target = tmp_path / "huge.pdf"
    with patch("download.requests.get", return_value=fake_response):
        with pytest.raises(ValueError, match="too large"):
            download_pdf("https://bochum.de/huge.pdf", target)


def test_download_pdf_rejects_non_200(tmp_path):
    fake_response = MagicMock()
    fake_response.status_code = 404
    fake_response.headers = {}
    target = tmp_path / "missing.pdf"
    with patch("download.requests.get", return_value=fake_response):
        with pytest.raises(RuntimeError, match="HTTP 404"):
            download_pdf("https://bochum.de/missing.pdf", target)
