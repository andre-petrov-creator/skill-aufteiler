"""Persist scrape artifacts into the lead folder."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import nodriver as uc


class OutputWriter:
    """All file writes for a successful scrape happen here."""

    def __init__(self, target_folder: Path) -> None:
        self.target = target_folder
        self.target.mkdir(parents=True, exist_ok=True)
        self.log_file = self.target / "scraper.log"
        self.logger = self._make_logger()

    def _make_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"immoscout.{self.target.name}")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(self.log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
        logger.addHandler(ch)
        return logger

    def log(self, msg: str) -> None:
        self.logger.info(msg)

    def backup_existing(self) -> None:
        existing = [p for p in self.target.glob("expose*") if p.is_file()]
        if not existing:
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.target / "Backup" / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        for f in existing:
            shutil.move(str(f), str(backup_dir / f.name))

    def write_expose_json(self, data: Dict[str, Any]) -> None:
        target = self.target / "expose.json"
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"WRITE expose.json ({target.stat().st_size} bytes)")

    def write_keyvalues(self, kv: Dict[str, Any]) -> None:
        target = self.target / "expose_keyvalues.json"
        target.write_text(json.dumps(kv, indent=2, ensure_ascii=False), encoding="utf-8")
        self.log(f"WRITE expose_keyvalues.json")

    def write_html(self, html: str) -> None:
        target = self.target / "expose.html"
        target.write_text(html, encoding="utf-8")
        self.log(f"WRITE expose.html ({target.stat().st_size} bytes)")

    def write_final_url(self, url: str) -> None:
        (self.target / "final_url.txt").write_text(url, encoding="utf-8")
        self.log(f"WRITE final_url.txt")

    def download_images(self, image_urls: List[str]) -> int:
        """Download images using a fresh nodriver context for same-origin requests.

        Returns number of images successfully downloaded.
        """
        if not image_urls:
            return 0
        bilder_dir = self.target / "bilder"
        bilder_dir.mkdir(exist_ok=True)
        return asyncio.run(self._download_images_async(image_urls, bilder_dir))

    async def _download_images_async(self, urls: List[str], bilder_dir: Path) -> int:
        import urllib.request
        ok = 0
        for idx, url in enumerate(urls, start=1):
            ext = url.split(".")[-1].split("?")[0].lower()
            if ext not in ("jpg", "jpeg", "png", "webp"):
                ext = "jpg"
            target = bilder_dir / f"bild_{idx:02d}.{ext}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    target.write_bytes(resp.read())
                self.log(f"DOWNLOAD {target.name} ({target.stat().st_size} bytes)")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                self.log(f"DOWNLOAD FAIL bild_{idx:02d} {exc}")
        return ok

    def render_pdf_and_screenshot(self, url: str) -> None:
        """Re-open the page in nodriver to produce a print-PDF and a screenshot.
        Reusing the orchestrator's session would be cleaner, but a second open
        is acceptable for now (one extra page-load on success).
        """
        asyncio.run(self._render_async(url))

    async def _render_async(self, url: str) -> None:
        import base64
        from nodriver import cdp

        start = time.time()
        # NOTE: Imperva blocks headless against ImmoScout — use headed.
        browser = await uc.start(headless=False)
        try:
            page = await browser.get(url)
            await asyncio.sleep(5)
            await page.save_screenshot(str(self.target / "expose-screenshot.png"))
            self.log(f"WRITE expose-screenshot.png")
            try:
                result = await page.send(cdp.page.print_to_pdf(
                    landscape=False,
                    print_background=True,
                    prefer_css_page_size=True,
                ))
                pdf_b64 = result[0] if isinstance(result, tuple) else result
                pdf_bytes = base64.b64decode(pdf_b64)
                (self.target / "expose.pdf").write_bytes(pdf_bytes)
                self.log(f"WRITE expose.pdf ({len(pdf_bytes)} bytes)")
            except Exception as exc:  # noqa: BLE001
                self.log(f"PDF FAIL {exc}")
        finally:
            browser.stop()
            self.log(f"RENDER PDF/SCREENSHOT done in {time.time()-start:.1f}s")
