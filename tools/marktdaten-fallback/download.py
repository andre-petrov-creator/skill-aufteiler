"""PDF-Download mit Cache-Layer."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests


CACHE_DIR = Path(__file__).resolve().parent / "cache"
MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
DOWNLOAD_TIMEOUT_S = 60


def _slug(text: str) -> str:
    """Normalize string for filename."""
    text = text.lower().strip()
    text = re.sub(
        r"[äöüß]",
        lambda m: {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}[m.group(0)],
        text,
    )
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def cache_path_for(stadt: str, typ: str, jahr: int) -> Path:
    """Cache-Pfad fuer (stadt, typ, jahr). Erzeugt cache/ falls nicht existiert."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_slug(stadt)}-{typ}-{jahr}.pdf"
    return CACHE_DIR / filename


def cache_hit(cache_file: Path, notion_stand_iso: Optional[str]) -> bool:
    """True wenn Cache-Datei existiert UND nicht aelter ist als der Notion-Stand."""
    if not cache_file.exists():
        return False
    if notion_stand_iso is None:
        return True
    try:
        notion_stand = datetime.fromisoformat(notion_stand_iso).timestamp()
    except ValueError:
        return True  # ungültiges Datum → Cache nicht invalidieren
    cache_mtime = cache_file.stat().st_mtime
    return cache_mtime >= notion_stand


def download_pdf(url: str, target_path: Path) -> Path:
    """Laedt PDF, schreibt nach target_path. Wirft bei >50 MB oder Non-200."""
    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_S, stream=False)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} bei {url}")
    content_length = int(response.headers.get("Content-Length", "0") or "0")
    if content_length > MAX_PDF_SIZE_BYTES:
        raise ValueError(f"PDF too large: {content_length} bytes > {MAX_PDF_SIZE_BYTES}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(response.content)
    return target_path
