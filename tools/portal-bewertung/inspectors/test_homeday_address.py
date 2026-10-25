"""End-to-End-Test für Homeday Adress-Eingabe.

Lädt Preisatlas, klickt Cookies weg, probiert mehrere Adress-Feld-Selektoren
durch, tippt die volle Adresse + Enter, macht Screenshots vor/nach. Hält den
Browser offen, damit der User die Ergebnis-Seite betrachten kann.
"""
from __future__ import annotations

import io
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJ_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJ_ROOT / "runs"
BERLIN_TZ = timezone(timedelta(hours=2))

URL = "https://www.homeday.de/de/preisatlas"
ADDRESS = "Prosperstraße 59, 45357 Essen"

COOKIE_CANDIDATES = [
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    'button:has-text("Alle akzeptieren")',
    'a:has-text("Alle akzeptieren")',
]

ADDRESS_INPUT_CANDIDATES = [
    'input[placeholder*="straße" i]',
    'input[placeholder*="Adresse" i]',
    'input[placeholder*="Ort" i]',
    'input[type="search"]',
    'input[role="combobox"]',
    'input.search-input',
    '[data-testid*="address"] input',
    '[data-testid*="search"] input',
    'input[name*="address"]',
    'input[name*="search"]',
    # Catch-all: erstes sichtbares text-input auf der Seite
    'input[type="text"]:visible',
    'input:visible',
]


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _dismiss_cookies(page, max_wait_s: float = 15.0) -> tuple[bool, str]:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        for sel in COOKIE_CANDIDATES:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=2_000)
                    return True, sel
            except Exception:
                continue
        page.wait_for_timeout(1_000)
    return False, ""


def _find_address_input(page, max_wait_s: float = 10.0) -> tuple[object, str]:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        for sel in ADDRESS_INPUT_CANDIDATES:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    return loc, sel
            except Exception:
                continue
        page.wait_for_timeout(500)
    return None, ""


def main() -> int:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    p_after_cookie = RUNS_DIR / f"{ts}_homeday_03_form_ready.png"
    p_after_type = RUNS_DIR / f"{ts}_homeday_04_after_typing.png"
    p_after_enter = RUNS_DIR / f"{ts}_homeday_05_after_enter.png"
    p_result = RUNS_DIR / f"{ts}_homeday_06_result.png"

    from playwright.sync_api import sync_playwright

    print(f">>> Öffne {URL} (headed)…", file=sys.stderr, flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3_000)

        dismissed, sel_used = _dismiss_cookies(page)
        print(
            f">>> Cookies: {'weg via ' + repr(sel_used) if dismissed else 'NICHT geklickt'}",
            file=sys.stderr, flush=True,
        )
        page.wait_for_timeout(1_500)
        page.screenshot(path=str(p_after_cookie), full_page=False)
        print(f">>> Screenshot 03 (Formular sichtbar): {p_after_cookie.name}", file=sys.stderr, flush=True)

        input_loc, input_sel = _find_address_input(page)
        if input_loc is None:
            print(">>> KEIN Adress-Feld gefunden — alle Kandidaten verworfen.", file=sys.stderr, flush=True)
            print(f">>> Browser bleibt offen — schließe ihn manuell.", file=sys.stderr, flush=True)
            while not page.is_closed():
                time.sleep(2)
            browser.close()
            return 1

        print(f">>> Adress-Feld gefunden: {input_sel!r}", file=sys.stderr, flush=True)

        input_loc.click()
        page.wait_for_timeout(300)
        input_loc.evaluate("el => el.value = ''")
        input_loc.press_sequentially(ADDRESS, delay=80)
        print(f">>> Eingetippt: {ADDRESS!r}", file=sys.stderr, flush=True)
        page.wait_for_timeout(1_500)  # Autocomplete-Dropdown abwarten
        page.screenshot(path=str(p_after_type), full_page=False)
        print(f">>> Screenshot 04 (nach Tippen): {p_after_type.name}", file=sys.stderr, flush=True)

        input_loc.press("Enter")
        print(">>> Enter gedrückt — warte auf Seitenwechsel…", file=sys.stderr, flush=True)
        page.wait_for_timeout(3_000)
        page.screenshot(path=str(p_after_enter), full_page=False)
        print(f">>> Screenshot 05 (3s nach Enter): {p_after_enter.name}", file=sys.stderr, flush=True)

        page.wait_for_timeout(5_000)
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        page.screenshot(path=str(p_result), full_page=True)
        print(
            f">>> Screenshot 06 (Result, full_page): {p_result.name}",
            file=sys.stderr, flush=True,
        )
        print(f">>> URL nach Enter: {page.url}", file=sys.stderr, flush=True)
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
