"""Browser-Setup — Chromium-Launch mit Locale + Viewport-Defaults."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass
class BrowserConfig:
    headless: bool = False
    viewport_width: int = 1440
    viewport_height: int = 1600
    locale: str = "de-DE"
    timezone_id: str = "Europe/Berlin"
    default_timeout_ms: int = 15_000


def launch_browser(playwright: Any, cfg: BrowserConfig) -> Tuple[Any, Any, Any]:
    """Startet Chromium und gibt (browser, context, page) zurück.

    `playwright` ist das Objekt aus `sync_playwright().start()` oder dem
    `with sync_playwright() as p`-Kontext-Manager.
    """
    browser = playwright.chromium.launch(headless=cfg.headless)
    context = browser.new_context(
        locale=cfg.locale,
        timezone_id=cfg.timezone_id,
        viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
    )
    page = context.new_page()
    page.set_default_timeout(cfg.default_timeout_ms)
    return browser, context, page
