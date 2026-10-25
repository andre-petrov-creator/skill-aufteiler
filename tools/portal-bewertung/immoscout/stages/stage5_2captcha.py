"""Stage 5: nodriver + 2Captcha API. Only runs if TWOCAPTCHA_API_KEY is set."""
from __future__ import annotations

import asyncio
import os
import re
import time

import nodriver as uc

from .base import ScraperStage, ScrapeResult


class Stage5TwoCaptcha(ScraperStage):
    name = "stage5_2captcha"
    default_timeout_s = 180.0  # captcha solving can take a while
    settle_seconds = 5.0

    def __init__(self) -> None:
        self.api_key = os.environ.get("TWOCAPTCHA_API_KEY", "").strip()

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def scrape(self, url: str) -> ScrapeResult:
        if not self.is_enabled():
            return ScrapeResult(
                html="", final_url=url, stage_name=self.name, duration_s=0.0,
                error="TWOCAPTCHA_API_KEY not set — stage disabled",
            )
        return asyncio.run(self._scrape_async(url))

    async def _scrape_async(self, url: str) -> ScrapeResult:
        from twocaptcha import TwoCaptcha  # imported lazily

        start = time.time()
        solver = TwoCaptcha(self.api_key)
        browser = await uc.start(headless=True)
        try:
            page = await browser.get(url)
            await asyncio.sleep(self.settle_seconds)
            html = await page.get_content()

            # detect h/reCAPTCHA sitekey
            sitekey_match = re.search(r'data-sitekey="([^"]+)"', html)
            if sitekey_match:
                sitekey = sitekey_match.group(1)
                # try hCaptcha first (Imperva commonly uses it)
                try:
                    captured = solver.hcaptcha(sitekey=sitekey, url=url)
                except Exception:
                    captured = solver.recaptcha(sitekey=sitekey, url=url)
                token = captured.get("code", "")
                if token:
                    await page.evaluate(
                        f'document.querySelector("[name=h-captcha-response]").value = "{token}";'
                    )
                    await page.evaluate(
                        f'document.querySelector("[name=g-recaptcha-response]") && (document.querySelector("[name=g-recaptcha-response]").value = "{token}");'
                    )
                    # submit form
                    await page.evaluate("document.querySelector('form') && document.querySelector('form').submit();")
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
