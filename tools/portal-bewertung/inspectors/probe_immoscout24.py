"""Probe-Skript: ImmobilienScout24 — Wohnung + PLZ + Weiter (Step 2 fertig).

Klickt:
  1. Seite oeffnen
  2. 'Wohnung' klicken (gegen Cookie-Modal egal, programmatischer Klick geht durch)
  3. PLZ in #location-input
  4. Klick auf data-testid="location-next-button" (Enter funktioniert NICHT bei IS24)
  5. Screenshot + DOM-Dump der Folgeseite

Bleibt offen, damit der User sieht was kommt.

Lauf:
    .venv\\Scripts\\python.exe inspectors/probe_immoscout24.py --plz 45357
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
RUNS_DIR = PROJ_ROOT / "runs"
BERLIN_TZ = timezone(timedelta(hours=2))

URL = "https://www.immobilienscout24.de/immobilie-bewerten/"


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


JS_KILL_USERCENTRICS = """() => {
    let removed = 0;
    document.querySelectorAll(
        '#usercentrics-root, [id*="usercentrics"], [class*="usercentrics"]'
    ).forEach(el => { el.remove(); removed++; });
    return removed;
}"""


def _kill_usercentrics(page) -> int:
    """Entfernt Usercentrics-CMP-Container (Cookie-Banner) per DOM-Manipulation.

    Usercentrics nutzt Shadow DOM mit pointer-events: all — blockiert sonst
    alle programmatischen Klicks. Wir entfernen den Container komplett.
    """
    try:
        return int(page.evaluate(JS_KILL_USERCENTRICS))
    except Exception:
        return 0


def _shoot(page, slug: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{_ts()}_immoscout24_probe_{slug}.png"
    try:
        page.screenshot(path=str(p), full_page=True)
        print(f">>> Screenshot: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> Screenshot FAIL: {e}", file=sys.stderr, flush=True)
    return p


def _dump_dom(page, slug: str) -> Path:
    dom = page.evaluate(
        """() => ({
            url: location.href,
            headings: Array.from(document.querySelectorAll('h1,h2,h3'))
                .map(h => (h.innerText || '').trim()).filter(Boolean),
            inputs: Array.from(document.querySelectorAll('input')).map(e => ({
                type: e.type, name: e.name, id: e.id,
                placeholder: e.placeholder || null,
                ariaLabel: e.getAttribute('aria-label'),
                dataTestid: e.getAttribute('data-testid'),
                value: e.value || '',
                visible: e.offsetParent !== null,
            })),
            buttons: Array.from(document.querySelectorAll('button')).map(e => ({
                text: (e.innerText || '').trim().slice(0, 60),
                type: e.type, name: e.name, id: e.id,
                disabled: e.disabled,
                dataTestid: e.getAttribute('data-testid'),
                visible: e.offsetParent !== null,
            })).filter(b => b.text || b.dataTestid),
            selects: Array.from(document.querySelectorAll('select')).map(e => ({
                name: e.name, id: e.id,
                dataTestid: e.getAttribute('data-testid'),
                options: Array.from(e.options).map(o => o.text).slice(0, 30),
            })),
        })"""
    )
    p = RUNS_DIR / f"{_ts()}_immoscout24_probe_{slug}.json"
    p.write_text(json.dumps(dom, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f">>> DOM-Dump: {p.name} "
        f"(h={len(dom['headings'])}, in={len(dom['inputs'])}, "
        f"btn={len(dom['buttons'])}, sel={len(dom['selects'])})",
        file=sys.stderr, flush=True,
    )
    return p


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plz", default="45357")
    parser.add_argument("--wohnflaeche", default="80")
    parser.add_argument("--zimmer", default="3")
    parser.add_argument("--strasse", default="Prosperstraße")
    parser.add_argument("--hausnr", default="59")
    parser.add_argument("--keep-open", type=int, default=1500)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    print(f">>> Oeffne {URL}", file=sys.stderr, flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 1000},
        )
        page = ctx.new_page()

        # ---- Network-Sniffer: protokolliere relevante Requests/Responses ----
        network_log: list[dict] = []

        def _on_request(req) -> None:
            url = req.url
            if any(s in url for s in [
                "immobilienscout24", "is24", "/api/", "/valuation",
                "/property", "/price", "/pdf", "rle-wizard",
            ]):
                network_log.append({
                    "kind": "request",
                    "method": req.method,
                    "url": url[:300],
                    "resource_type": req.resource_type,
                    "headers": {k: v[:120] for k, v in req.headers.items()
                                if k.lower() in ("content-type", "authorization",
                                                  "x-csrf-token", "referer")},
                })

        def _on_response(resp) -> None:
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if any(s in url for s in [
                "/api/", "/valuation", "/property", "/price", "/pdf",
                "rle-wizard",
            ]) or (
                "immobilienscout24" in url and "json" in ct.lower()
            ):
                entry = {
                    "kind": "response",
                    "status": resp.status,
                    "url": url[:300],
                    "content_type": ct[:80],
                }
                try:
                    if "json" in ct.lower() and resp.status < 400:
                        body = resp.text()
                        entry["body_snippet"] = body[:2000]
                except Exception:
                    pass
                network_log.append(entry)

        page.on("request", _on_request)
        page.on("response", _on_response)
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3_000)

        # Usercentrics-Banner killen (blockiert sonst Klicks)
        removed = _kill_usercentrics(page)
        print(f">>> Usercentrics entfernt: {removed} Element(e)",
              file=sys.stderr, flush=True)
        page.wait_for_timeout(500)

        # ---- Step 1: 'Wohnung' ----
        print(">>> Step 1: 'Wohnung' klicken", file=sys.stderr, flush=True)
        _kill_usercentrics(page)  # bei Bedarf erneut
        try:
            page.locator('button:has-text("Wohnung")').first.click(timeout=5_000)
            print(">>>   OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(2_500)
        _shoot(page, "20_after_wohnung")

        # ---- Step 2: PLZ in #location-input ----
        print(">>> Step 2: PLZ", file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            page.locator("#location-input").fill(args.plz, timeout=4_000)
            print(f">>>   PLZ={args.plz} OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   PLZ FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(800)
        _shoot(page, "30_plz_typed")

        # ---- Step 3: Weiter via data-testid ----
        print(">>> Step 3: Weiter via [data-testid=location-next-button]",
              file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            btn = page.locator('[data-testid="location-next-button"]').first
            btn.click(timeout=5_000)
            print(">>>   Weiter OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Weiter FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(3_500)
        _shoot(page, "40_after_weiter")
        _dump_dom(page, "40_after_weiter_dom")

        # ---- Step 4: Wohnflaeche eintragen ----
        print(">>> Step 4: Wohnflaeche", file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            page.locator("#living_space").fill(args.wohnflaeche, timeout=4_000)
            print(f">>>   Wohnflaeche={args.wohnflaeche} OK",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Wohnflaeche FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(800)
        _shoot(page, "50_wohnflaeche_typed")

        # ---- Step 5: Weiter via area-next-button ----
        print(">>> Step 5: Weiter via [data-testid=area-next-button]",
              file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            btn = page.locator('[data-testid="area-next-button"]').first
            btn.click(timeout=5_000)
            print(">>>   Weiter OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Weiter FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(3_500)
        _shoot(page, "60_after_weiter")
        _dump_dom(page, "60_after_weiter_dom")

        # ---- Step 6: Zimmer (#room-stepper) ----
        print(">>> Step 6: Zimmer", file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            page.locator("#room-stepper").fill(args.zimmer, timeout=4_000)
            print(f">>>   Zimmer={args.zimmer} OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Zimmer FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(800)
        _shoot(page, "70_zimmer_typed")

        # ---- Step 7: Weiter via rooms-next-button ----
        print(">>> Step 7: Weiter via [data-testid=rooms-next-button]",
              file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            btn = page.locator('[data-testid="rooms-next-button"]').first
            btn.click(timeout=5_000)
            print(">>>   Weiter OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Weiter FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(3_500)
        _shoot(page, "80_after_weiter")
        _dump_dom(page, "80_after_weiter_dom")

        # ---- Step 8: Beweggrund 'Kauf' (Auto-Advance) ----
        print(">>> Step 8: 'Kauf' via [data-testid=option-BUY]",
              file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            btn = page.locator('[data-testid="option-BUY"]').first
            btn.click(timeout=5_000)
            print(">>>   Kauf OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Kauf FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(3_500)
        _shoot(page, "90_after_kauf")
        _dump_dom(page, "90_after_kauf_dom")

        # ---- Step 9: Strasse via Autocomplete (User-Sequenz) ----
        # Erst auf Adresse-Seite warten (kann nach Kauf-Klick laenger dauern)
        print(">>> Step 9: warte auf #street-input", file=sys.stderr, flush=True)
        try:
            page.wait_for_selector("#street-input", state="visible", timeout=15_000)
        except Exception as e:
            print(f">>>   wait FAIL: {e}", file=sys.stderr, flush=True)

        print(">>> Step 9: Strasse via Autocomplete "
              "(tippen -> ArrowDown -> Enter -> Tab)",
              file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            inp = page.locator("#street-input")
            inp.click(timeout=3_000)
            inp.fill(args.strasse, timeout=4_000)
            print(f">>>   getippt: {args.strasse!r}",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Strasse Fill FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(1_800)  # Autocomplete-Liste laden lassen
        _shoot(page, "100_strasse_typed")
        _dump_dom(page, "100_strasse_typed_dom")

        # User-Sequenz: ArrowDown -> Enter -> Tab
        try:
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
            page.wait_for_timeout(600)
            page.keyboard.press("Tab")
            print(">>>   ArrowDown+Enter+Tab gedrueckt",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Keys FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(800)
        _shoot(page, "105_strasse_selected")
        _dump_dom(page, "105_strasse_selected_dom")

        # ---- Step 10: Hausnummer (Cursor steht nach Tab schon im Feld) ----
        print(">>> Step 10: Hausnummer", file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            # Tab hat uns ins Hausnr-Feld gebracht. Falls nicht: explizit fokussieren.
            inp = page.locator("#house-number-input")
            inp.fill(args.hausnr, timeout=4_000)
            print(f">>>   Hausnummer={args.hausnr} OK",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Hausnummer FAIL: {e}", file=sys.stderr, flush=True)
        page.wait_for_timeout(800)
        _shoot(page, "110_hausnr_typed")

        # ---- Step 11: 'Zur Bewertung' (Submit) ----
        print(">>> Step 11: 'Zur Bewertung' via [data-testid=address-cta]",
              file=sys.stderr, flush=True)
        _kill_usercentrics(page)
        try:
            btn = page.locator('[data-testid="address-cta"]').first
            btn.click(timeout=5_000)
            print(">>>   Submit OK", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Submit FAIL: {e}", file=sys.stderr, flush=True)
        # Result-Seite kann laenger brauchen
        page.wait_for_timeout(8_000)
        _shoot(page, "120_result")
        _dump_dom(page, "120_result_dom")

        # ---- Network-Log dumpen ----
        try:
            net_path = RUNS_DIR / f"{_ts()}_immoscout24_probe_network.json"
            net_path.write_text(
                json.dumps(network_log, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(
                f">>> Network-Log: {net_path.name} "
                f"({len(network_log)} Eintraege)",
                file=sys.stderr, flush=True,
            )
        except Exception as e:
            print(f">>> Network-Log FAIL: {e}", file=sys.stderr, flush=True)

        print(
            f">>> Browser bleibt {args.keep_open}s offen. "
            "Schliesse Fenster zum Beenden.",
            file=sys.stderr, flush=True,
        )
        end = time.monotonic() + args.keep_open
        try:
            while not page.is_closed() and time.monotonic() < end:
                time.sleep(2)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
