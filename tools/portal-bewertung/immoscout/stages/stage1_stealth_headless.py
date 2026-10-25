"""Stage 1: playwright + stealth, headless. Fast first attempt."""
from __future__ import annotations

import time

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from .base import ScraperStage, ScrapeResult


class Stage1StealthHeadless(ScraperStage):
    name = "stage1_stealth_headless"
    default_timeout_s = 45.0
    settle_seconds = 6.0

    headless = True

    def scrape(self, url: str) -> ScrapeResult:
        start = time.time()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                )
                page = context.new_page()
                Stealth().apply_stealth_sync(page)
                page.goto(url, timeout=int(self.default_timeout_s * 1000), wait_until="domcontentloaded")
                page.wait_for_timeout(int(self.settle_seconds * 1000))
                html = page.content()
                final_url = page.url
                browser.close()
                return ScrapeResult(
                    html=html, final_url=final_url, stage_name=self.name,
                    duration_s=time.time() - start,
                )
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(
                html="", final_url=url, stage_name=self.name,
                duration_s=time.time() - start, error=str(exc),
            )
