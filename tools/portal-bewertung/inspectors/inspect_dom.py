"""Generischer DOM-Inspector für neue Portale.

Öffnet eine URL, klickt Best-Effort einen Cookie-Banner-Button, dumpt
alle Inputs/Selects/Radios/Submit-Kandidaten mit zugehörigen Label-Texten
in JSON + macht Screenshots. Hilft beim Setup neuer Portal-Adapter.

Lauf:
    .venv\\Scripts\\python.exe inspectors/inspect_dom.py <URL> [--out form_dump.json]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")  # type: ignore[assignment]

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

COOKIE_CANDIDATES = [
    'button:has-text("Akzeptieren")',
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Zustimmen")',
    'button:has-text("OK")',
    'button:has-text("geht klar")',
    'button:has-text("Geht klar")',
    'button:has-text("Verstanden")',
    'button:has-text("Schließen")',
    "#cookie-accept",
    "[id*='cookie'][id*='accept']",
]

INPUT_DUMP_JS = """els => els.map(e => {
    let lbl = '';
    let parent = e.parentElement;
    for (let i = 0; i < 4 && parent; i++) {
        const l = parent.querySelector('label, [class*=label]');
        if (l && l.textContent.trim()) { lbl = l.textContent.trim().slice(0, 80); break; }
        parent = parent.parentElement;
    }
    return {
        tag: 'INPUT',
        type: e.type,
        name: e.name,
        id: e.id,
        placeholder: e.placeholder || null,
        qaRef: e.getAttribute('qa-ref'),
        maxlength: e.maxLength > 0 ? e.maxLength : null,
        label: lbl,
        cssClasses: (e.className || '').toString(),
    };
})"""

SELECT_DUMP_JS = """els => els.map(e => {
    let lbl = '';
    let parent = e.parentElement;
    for (let i = 0; i < 4 && parent; i++) {
        const l = parent.querySelector('label, [class*=label]');
        if (l && l.textContent.trim()) { lbl = l.textContent.trim().slice(0, 80); break; }
        parent = parent.parentElement;
    }
    return {
        tag: 'SELECT',
        name: e.name,
        id: e.id,
        qaRef: e.getAttribute('qa-ref'),
        options: Array.from(e.options).map(o => o.text).slice(0, 12),
        label: lbl,
        cssClasses: (e.className || '').toString(),
    };
})"""

RADIO_DUMP_JS = """els => els.map(e => {
    let lbl = '';
    let parent = e.parentElement;
    for (let i = 0; i < 4 && parent; i++) {
        const txt = parent.innerText || '';
        if (txt && txt.length < 100) { lbl = txt.trim(); break; }
        parent = parent.parentElement;
    }
    return {
        tag: 'RADIO',
        name: e.name,
        id: e.id,
        qaRef: e.getAttribute('qa-ref'),
        value: e.value,
        label: lbl,
    };
})"""

BUTTON_DUMP_JS = """els => els.map(e => ({
    tag: 'BUTTON',
    text: (e.innerText || '').trim().slice(0, 60),
    type: e.type,
    qaRef: e.getAttribute('qa-ref'),
    name: e.name,
    id: e.id,
    cssClasses: (e.className || '').toString(),
})).filter(b => b.text || b.qaRef)"""


def _try_dismiss_cookies(page) -> bool:
    for selector in COOKIE_CANDIDATES:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2_000)
                return True
        except Exception:
            continue
    return False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="DOM-Inspector — dumpt Form-Elemente einer Bewertungs-Seite."
    )
    parser.add_argument("url", help="Start-URL des Portals.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("form_dump.json"),
        help="Output-Datei (Default: form_dump.json im CWD).",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        default=None,
        help="Screenshot-Pfad (Default: <out>.png).",
    )
    parser.add_argument(
        "--headless", action="store_true", default=True, help="Headless-Browser (Default).",
    )
    parser.add_argument(
        "--headed", dest="headless", action="store_false",
        help="Browser sichtbar starten.",
    )
    parser.add_argument(
        "--wait-after-load-ms", type=int, default=3_500,
        help="Wartezeit nach domcontentloaded für Cookie-Banner + JS-Hydration.",
    )
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 1600},
        )
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(args.wait_after_load_ms)

        dismissed = _try_dismiss_cookies(page)
        page.wait_for_timeout(1_500)

        inputs = page.eval_on_selector_all("input", INPUT_DUMP_JS)
        selects = page.eval_on_selector_all("select", SELECT_DUMP_JS)
        radios = page.eval_on_selector_all('input[type="radio"]', RADIO_DUMP_JS)
        buttons = page.eval_on_selector_all("button", BUTTON_DUMP_JS)

        dump = {
            "url": args.url,
            "cookie_dismissed": dismissed,
            "inputs": inputs,
            "selects": selects,
            "radios": radios,
            "buttons": buttons,
        }
        args.out.write_text(
            json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        screenshot_path = args.screenshot or args.out.with_suffix(".png")
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            screenshot_path = None  # type: ignore[assignment]

        print(
            f"Inputs: {len(inputs)} | Selects: {len(selects)} | "
            f"Radios: {len(radios)} | Buttons: {len(buttons)} → {args.out}"
            + (f" (Screenshot: {screenshot_path})" if screenshot_path else ""),
            file=sys.stderr,
        )
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
