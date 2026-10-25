"""Tiefen-Dump der Homeday-Ergebnisseite.

Geht direkt per Deep-Link auf die Result-URL, klickt Cookies weg, scrollt
durch die ganze Seite (lazy-load), macht einen Full-Page-Screenshot mit
großem Viewport, schreibt body-Text + alle sichtbaren Elemente mit
qa-ref/data-* Attributen + Farb-Sample an der Adress-Pin-Position auf
der Karte.
"""
from __future__ import annotations

import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJ_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJ_ROOT / "runs"
BERLIN_TZ = timezone(timedelta(hours=2))

# Deep-Link aus dem voherigen Lauf — überspringt das Formular
RESULT_URL = (
    "https://www.homeday.de/de/preisatlas/essen/prosperstrasse+59,+45357"
    "?map_layer=standard&marketing_type=sell&property_type=apartment"
)

COOKIE_CANDIDATES = [
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
]

JS_HARVEST = """() => {
    // Strukturierte Sicht auf alle Text-tragenden Elemente mit data-*/qa-ref
    const out = [];
    document.querySelectorAll('*').forEach(el => {
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return;
        const ownText = Array.from(el.childNodes)
            .filter(n => n.nodeType === 3)
            .map(n => n.textContent.trim()).join(' ').trim();
        const dataAttrs = {};
        for (const a of el.attributes) {
            if (a.name.startsWith('data-') || a.name === 'qa-ref' || a.name === 'aria-label') {
                dataAttrs[a.name] = a.value;
            }
        }
        const hasDataAttr = Object.keys(dataAttrs).length > 0;
        if (!ownText && !hasDataAttr) return;
        if (ownText.length > 0 && ownText.length < 200) {
            out.push({
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                classes: (el.className || '').toString().slice(0, 120),
                text: ownText,
                dataAttrs: dataAttrs,
                color: cs.color,
                bg: cs.backgroundColor,
            });
        }
    });
    return out;
}"""


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _dismiss_cookies(page, max_wait_s: float = 15.0) -> bool:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        for sel in COOKIE_CANDIDATES:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=2_000)
                    return True
            except Exception:
                continue
        page.wait_for_timeout(1_000)
    return False


def main() -> int:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    p_full = RUNS_DIR / f"{ts}_homeday_result_fullpage.png"
    p_viewport = RUNS_DIR / f"{ts}_homeday_result_viewport.png"
    p_text = RUNS_DIR / f"{ts}_homeday_result_text.txt"
    p_harvest = RUNS_DIR / f"{ts}_homeday_result_harvest.json"

    from playwright.sync_api import sync_playwright

    print(f">>> Direkter Deeplink: {RESULT_URL}", file=sys.stderr, flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1600, "height": 1400},
        )
        page = ctx.new_page()
        page.goto(RESULT_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4_000)

        if _dismiss_cookies(page):
            print(">>> Cookies weg.", file=sys.stderr, flush=True)
        page.wait_for_timeout(2_000)

        # Karte + Charts haben oft lazy-loaded Content — Scrollen triggert das
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(800)
        for y in (400, 800, 1200, 1600, 2000, 2400, 0):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(500)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass

        page.screenshot(path=str(p_viewport), full_page=False)
        page.screenshot(path=str(p_full), full_page=True)
        print(f">>> Viewport-Screenshot: {p_viewport.name}", file=sys.stderr, flush=True)
        print(f">>> FullPage-Screenshot: {p_full.name}", file=sys.stderr, flush=True)

        body_text = page.evaluate(
            """() => {
                const texts = [];
                document.querySelectorAll('*').forEach(el => {
                    const cs = getComputedStyle(el);
                    if (cs.display === 'none' || cs.visibility === 'hidden') return;
                    const own = Array.from(el.childNodes)
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim()).filter(t => t).join(' ');
                    if (own) texts.push(own);
                });
                return texts.join('\\n');
            }"""
        )
        p_text.write_text(body_text or "", encoding="utf-8")
        print(f">>> Body-Text ({len(body_text)} chars): {p_text.name}", file=sys.stderr, flush=True)

        harvest = page.evaluate(JS_HARVEST)
        p_harvest.write_text(
            json.dumps(harvest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f">>> Harvest ({len(harvest)} Elemente): {p_harvest.name}", file=sys.stderr, flush=True)

        print(f">>> Browser bleibt offen. Schließe das Fenster zum Beenden.", file=sys.stderr, flush=True)
        try:
            while not page.is_closed():
                time.sleep(2)
        except Exception:
            pass
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
