"""Stage 3: nodriver headless. The proven baseline against Imperva."""
from __future__ import annotations

import asyncio
import time

import nodriver as uc

from .base import ScraperStage, ScrapeResult


class Stage3Nodriver(ScraperStage):
    name = "stage3_nodriver"
    default_timeout_s = 60.0
    settle_seconds = 8.0  # let Imperva JS challenge run

    def __init__(self, headless: bool = False) -> None:
        # Default False: headless mode triggers Imperva bot detection.
        # Probe on 2026-05-22 confirmed headed mode sails through.
        self.headless = headless

    def scrape(self, url: str) -> ScrapeResult:
        return asyncio.run(self._scrape_async(url))

    async def _scrape_async(self, url: str) -> ScrapeResult:
        start = time.time()
        browser = await uc.start(headless=self.headless)
        try:
            page = await browser.get(url)
            await asyncio.sleep(self.settle_seconds)
            html = await page.get_content()
            final_url = await page.evaluate("document.location.href") or url
            return ScrapeResult(
                html=html,
                final_url=final_url,
                stage_name=self.name,
                duration_s=time.time() - start,
            )
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(
                html="",
                final_url=url,
                stage_name=self.name,
                duration_s=time.time() - start,
                error=str(exc),
            )
        finally:
            browser.stop()
