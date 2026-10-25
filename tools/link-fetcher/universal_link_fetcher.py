"""
Universal Link Fetcher.

Capability-Eskalation:
  Stage 1: Playwright headless Stealth (default)
  Stage 2: nodriver (sichtbares Fenster, bei Captcha-Marker)
  Stage 3: 2Captcha (NUR fuer immobilienscout24.de, bei Captcha nach Stage 2)

Aufruf:
  python universal_link_fetcher.py <url> <output_dir>

Exit-Codes:
  0 = ok
  1 = Stage 1 + 2 (+3) gescheitert
  2 = unsupported Content-Type (z.B. weder PDF noch HTML)
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

# Absoluter Import — link-fetcher hat Bindestrich, kein Python-Package moeglich
sys.path.insert(0, str(Path(__file__).resolve().parent))
from stages import (  # noqa: E402
    has_captcha_marker,
    stage1_playwright_headless,
    stage2_nodriver,
    stage3_2captcha,
)


IMMOSCOUT_DOMAIN = "immobilienscout24.de"


def fetch(url: str, output_dir: Path) -> int:
    """Returns exit-code (0=ok)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # HEAD-Request fuer Content-Type-Routing
    try:
        head = requests.head(url, allow_redirects=True, timeout=15)
        content_type = head.headers.get("Content-Type", "").lower().split(";")[0].strip()
    except Exception as e:
        print(f"HEAD failed: {e} — falle auf HTML-Stage zurueck", file=sys.stderr)
        content_type = "text/html"

    # PDF: direkt downloaden
    if "application/pdf" in content_type:
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            (output_dir / "Exposé Webseite.pdf").write_bytes(r.content)
            (output_dir / "final_url.txt").write_text(r.url, encoding="utf-8")
            (output_dir / "scraper.log").write_text("stage=0\nstatus=ok\ntype=pdf-direct\n",
                                                    encoding="utf-8")
            print("ok (Stage 0 PDF-Direct-Download)")
            return 0
        except Exception as e:
            print(f"PDF download failed: {e}", file=sys.stderr)
            return 1

    # HTML: Stage-Kaskade
    if "text/html" in content_type or not content_type:
        ok, html_or_err = stage1_playwright_headless(url, output_dir)
        if not ok:
            print(f"Stage 1 failed: {html_or_err}", file=sys.stderr)
            return 1
        if not has_captcha_marker(html_or_err):
            (output_dir / "scraper.log").write_text("stage=1\nstatus=ok\n", encoding="utf-8")
            print("ok (Stage 1 Playwright headless)")
            return 0

        # Captcha erkannt → Stage 2
        ok2, html2_or_err = stage2_nodriver(url, output_dir)
        if not ok2:
            print(f"Stage 2 failed: {html2_or_err}", file=sys.stderr)
            return 1
        if not has_captcha_marker(html2_or_err):
            (output_dir / "scraper.log").write_text("stage=2\nstatus=ok\n", encoding="utf-8")
            print("ok (Stage 2 nodriver)")
            return 0

        # Stage 2 immer noch Captcha → Stage 3 nur fuer ImmoScout
        host = (urlparse(url).hostname or "").lower()
        if IMMOSCOUT_DOMAIN in host:
            ok3, html3_or_err = stage3_2captcha(url, output_dir)
            if ok3:
                (output_dir / "scraper.log").write_text("stage=3\nstatus=ok\n", encoding="utf-8")
                print("ok (Stage 3 2Captcha)")
                return 0
            print(f"Stage 3 failed: {html3_or_err}", file=sys.stderr)
        else:
            print(f"Captcha persistent, Domain {host} unsupported fuer Stage 3",
                  file=sys.stderr)
        return 1

    # Anderer Content-Type (json, zip, image, ...) als Blob speichern
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        ext = content_type.split("/")[-1] or "bin"
        (output_dir / f"link_content.{ext}").write_bytes(r.content)
        (output_dir / "final_url.txt").write_text(r.url, encoding="utf-8")
        (output_dir / "scraper.log").write_text(
            f"stage=0\nstatus=ok\ntype=blob\ncontent_type={content_type}\n",
            encoding="utf-8",
        )
        print(f"ok (Blob-Save, Content-Type={content_type})")
        return 0
    except Exception as e:
        print(f"Blob save failed: {e}", file=sys.stderr)
        return 2


def main():
    if len(sys.argv) < 3:
        print("USAGE: universal_link_fetcher.py <url> <output_dir>", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    output_dir = Path(sys.argv[2])
    sys.exit(fetch(url, output_dir))


if __name__ == "__main__":
    main()
