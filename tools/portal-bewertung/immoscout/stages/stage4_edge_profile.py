"""Stage 4: nodriver + Imperva cookies read from the user's running Edge profile.

Edge stores cookies in an encrypted SQLite DB. We copy it to %TEMP% to avoid the
running-Edge lock, then pull cookies for the relevant domains.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import List

import nodriver as uc

from .base import ScraperStage, ScrapeResult

EDGE_COOKIE_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data" / "Default" / "Network" / "Cookies",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data" / "Default" / "Cookies",
]

DOMAIN_FILTERS = ("immobilienscout24.de", "incapsula.com", "imperva.com")


def _read_edge_cookies() -> List[dict]:
    src = next((p for p in EDGE_COOKIE_PATHS if p.exists()), None)
    if src is None:
        return []
    tmpdir = Path(tempfile.gettempdir())
    dst = tmpdir / f"edge_cookies_{os.getpid()}.sqlite"
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        return []
    try:
        conn = sqlite3.connect(str(dst))
        cur = conn.cursor()
        cur.execute("SELECT host_key, name, value, path, expires_utc, is_secure FROM cookies")
        rows = cur.fetchall()
        conn.close()
    finally:
        dst.unlink(missing_ok=True)
    cookies = []
    for host, name, value, path, expires, secure in rows:
        if not any(d in host for d in DOMAIN_FILTERS):
            continue
        # Edge has encrypted values for new cookies; we can only inject decrypted ones.
        # Imperva session cookies are usually plaintext.
        if not isinstance(value, str) or not value:
            continue
        cookies.append({
            "name": name, "value": value, "domain": host,
            "path": path, "secure": bool(secure),
        })
    return cookies


class Stage4EdgeProfile(ScraperStage):
    name = "stage4_edge_profile"
    default_timeout_s = 60.0
    settle_seconds = 5.0

    def scrape(self, url: str) -> ScrapeResult:
        return asyncio.run(self._scrape_async(url))

    async def _scrape_async(self, url: str) -> ScrapeResult:
        start = time.time()
        cookies = _read_edge_cookies()
        browser = await uc.start(headless=False)
        try:
            page = await browser.get("https://www.immobilienscout24.de/")
            # inject cookies — nodriver exposes set_cookies on tab/browser
            if cookies:
                try:
                    await browser.cookies.set_all(cookies)
                except Exception:
                    pass  # best effort — some keys can't be set
            page = await browser.get(url)
            await asyncio.sleep(self.settle_seconds)
            html = await page.get_content()
            final_url = await page.evaluate("document.location.href") or url
            return ScrapeResult(
                html=html, final_url=final_url, stage_name=self.name,
                duration_s=time.time() - start,
            )
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(
                html="", final_url=url, stage_name=self.name,
                duration_s=time.time() - start, error=str(exc),
            )
        finally:
            browser.stop()
