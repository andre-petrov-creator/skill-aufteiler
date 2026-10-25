"""Browser-Offen-Halter für interaktives Portal-Sparring.

Öffnet eine URL in einem sichtbaren Browser, macht automatisch zwei
Screenshots (vor + nach Cookie-Dismiss) und hält den Browser offen,
bis der User das Fenster schließt — sodass der User selbst klicken
und Screenshots an Claude schicken kann.

Lauf:
    .venv\\Scripts\\python.exe inspectors/open_portal.py <URL> [--name homeday]
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

RUNS_DIR = PROJ_ROOT / "runs"
BERLIN_TZ = timezone(timedelta(hours=2))

COOKIE_CANDIDATES = [
    # Cookiebot (homeday.de + viele andere)
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    # Generisch — <button> und <a>
    'button:has-text("Alle akzeptieren")',
    'a:has-text("Alle akzeptieren")',
    'button:has-text("Akzeptieren")',
    'a:has-text("Akzeptieren")',
    'button:has-text("Zustimmen")',
    'button:has-text("Einverstanden")',
    'button:has-text("Verstanden")',
    'button:has-text("geht klar")',
    'button:has-text("Geht klar")',
    'button:has-text("OK")',
    'button:has-text("Schließen")',
    '[role="button"]:has-text("Alle akzeptieren")',
    '[role="button"]:has-text("Akzeptieren")',
    "#cookie-accept",
    "[id*='cookie'][id*='accept']",
    "[data-testid*='accept']",
]


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _try_dismiss_cookies(page, max_wait_s: float = 15.0) -> tuple[bool, str]:
    """Pollt bis zu max_wait_s Sekunden nach einem klickbaren Cookie-Banner."""
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        for selector in COOKIE_CANDIDATES:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=2_000)
                    return True, selector
            except Exception:
                continue
        page.wait_for_timeout(1_000)
    return False, ""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Öffnet eine Portal-URL im sichtbaren Browser und hält offen."
    )
    parser.add_argument("url")
    parser.add_argument(
        "--name", default="portal",
        help="Slug für Screenshot-Dateinamen (z.B. 'homeday')",
    )
    parser.add_argument(
        "--wait-after-load-ms", type=int, default=3_000,
        help="Wartezeit nach domcontentloaded für Hydration/Cookie-Banner.",
    )
    args = parser.parse_args(argv)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    p1 = RUNS_DIR / f"{ts}_{args.name}_01_initial.png"
    p2 = RUNS_DIR / f"{ts}_{args.name}_02_after_cookies.png"

    from playwright.sync_api import sync_playwright

    print(f">>> Öffne {args.url} (headed)…", file=sys.stderr, flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(args.wait_after_load_ms)

        page.screenshot(path=str(p1), full_page=True)
        print(f">>> Screenshot 01 (mit Cookie-Banner): {p1.name}", file=sys.stderr, flush=True)

        dismissed, sel_used = _try_dismiss_cookies(page)
        page.wait_for_timeout(1_500)
        if dismissed:
            print(f">>> Cookies weggeklickt mit {sel_used!r}", file=sys.stderr, flush=True)
        else:
            print(">>> KEIN Cookie-Banner-Button auto-erkannt — bitte manuell.", file=sys.stderr, flush=True)

        page.screenshot(path=str(p2), full_page=True)
        print(f">>> Screenshot 02 (nach Cookie-Dismiss): {p2.name}", file=sys.stderr, flush=True)

        print(
            f">>> Browser bleibt offen auf {args.url}.\n"
            f">>> Schließe das Browser-Fenster, um zu beenden.\n",
            file=sys.stderr, flush=True,
        )
        try:
            while not page.is_closed():
                time.sleep(2)
        except Exception:
            pass

        print(">>> Browser geschlossen, beende.", file=sys.stderr, flush=True)
        try:
            browser.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
