"""Probe-Skript: Interhyp-Wizard headed durchklicken.

Klickt selbst durch Wizard-Schritte 1-4 (Immobilienart, Adresse mit
Autocomplete-Click, Beweggrund, Miete) und haelt den Browser am Ende
offen.

Lauf:
    .venv\\Scripts\\python.exe inspectors/probe_interhyp.py
"""
from __future__ import annotations

import argparse
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

URL = "https://www.interhyp.de/rechner/immobilienbewertung/"

COOKIE_CANDIDATES = [
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Akzeptieren")',
    'button:has-text("Zustimmen")',
    'button:has-text("OK")',
]


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _shoot(page, slug: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{_ts()}_interhyp_probe_{slug}.png"
    try:
        page.screenshot(path=str(p), full_page=True)
        print(f">>> Screenshot: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> Screenshot FAIL: {e}", file=sys.stderr, flush=True)


def _try_dismiss_cookies(page, max_wait_s: float = 6.0) -> None:
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        for sel in COOKIE_CANDIDATES:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=2_000)
                    print(f">>> Cookies weggeklickt: {sel!r}", file=sys.stderr, flush=True)
                    return
            except Exception:
                continue
        page.wait_for_timeout(500)
    print(">>> Kein Cookie-Banner gefunden.", file=sys.stderr, flush=True)


def _try_fill_input(page, label_text: str, value: str, prefix: str) -> bool:
    """Versucht ein Input zu finden + fuellen ueber mehrere Selektor-Strategien."""
    strategies = [
        ("get_by_label exact", lambda: page.get_by_label(label_text, exact=True)),
        ("get_by_label fuzzy", lambda: page.get_by_label(label_text)),
        ("get_by_placeholder", lambda: page.get_by_placeholder(label_text)),
        ("input[placeholder*=]", lambda: page.locator(f'input[placeholder*="{label_text}"]')),
        ("input[aria-label*=]", lambda: page.locator(f'input[aria-label*="{label_text}"]')),
        ("input[name*=]", lambda: page.locator(f'input[name*="{label_text.lower()}"]')),
    ]
    for name, make_loc in strategies:
        try:
            loc = make_loc().first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(value, timeout=4_000)
                print(f">>>   {prefix}: '{label_text}' = {value!r} via {name}", file=sys.stderr, flush=True)
                return True
        except Exception:
            continue
    print(f">>>   {prefix}: '{label_text}' NICHT GEFUNDEN.", file=sys.stderr, flush=True)
    return False


def _try_click_text(page, text: str, prefix: str) -> bool:
    """Versucht etwas Klickbares mit gegebenem Text zu finden + zu klicken."""
    strategies = [
        ("label:has-text", lambda: page.locator(f'label:has-text("{text}")')),
        ("[role='radio']:has-text", lambda: page.locator(f'[role="radio"]:has-text("{text}")')),
        ("button:has-text", lambda: page.locator(f'button:has-text("{text}")')),
        ("get_by_role radio", lambda: page.get_by_role("radio", name=text)),
        ("get_by_role button", lambda: page.get_by_role("button", name=text)),
        ("text=", lambda: page.locator(f'text="{text}"')),
    ]
    for name, make_loc in strategies:
        try:
            loc = make_loc().first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3_000)
                print(f">>>   {prefix}: Klick '{text}' via {name}", file=sys.stderr, flush=True)
                return True
        except Exception:
            continue
    print(f">>>   {prefix}: Klick '{text}' NICHT MOEGLICH.", file=sys.stderr, flush=True)
    return False


def _click_strasse_dropdown_item(page, strasse: str, ort: str) -> bool:
    """Klickt im Autocomplete-Dropdown den Eintrag mit Strasse + Ort."""
    target = f"{strasse}, {ort}"
    for sel in [
        f'li:has-text("{target}")',
        f'[role="option"]:has-text("{target}")',
        f'div[role="listbox"] >> text="{target}"',
        f'text="{target}"',
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2_000)
                print(f">>>   Dropdown-Klick exakt: {sel!r}", file=sys.stderr, flush=True)
                return True
        except Exception:
            continue

    for sel in [f'li:has-text("{strasse}")', f'[role="option"]:has-text("{strasse}")']:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2_000)
                print(f">>>   Dropdown-Klick fallback: {sel!r}", file=sys.stderr, flush=True)
                return True
        except Exception:
            continue
    print(">>>   Dropdown nicht gefunden.", file=sys.stderr, flush=True)
    return False


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plz", default="45357")
    parser.add_argument("--ort", default="Essen")
    parser.add_argument("--strasse", default="Prosperstraße")
    parser.add_argument("--hausnr", default="59")
    parser.add_argument("--miete", default="850")
    parser.add_argument("--wohnflaeche", default="80")
    parser.add_argument("--zimmer", default="3")
    parser.add_argument("--baujahr", default="1965")
    parser.add_argument("--sanierung", choices=["ja", "nein"], default="nein")
    parser.add_argument("--sanierungsjahr", default="")
    parser.add_argument(
        "--ausstattung", choices=["Einfach", "Gehoben", "Luxus"], default="Einfach"
    )
    parser.add_argument("--aufzug", action="store_true")
    parser.add_argument("--parkplatz", action="store_true")
    parser.add_argument("--parkplatz-groesse", type=int, default=12)
    parser.add_argument("--terrasse", action="store_true")
    parser.add_argument("--balkon", action="store_true")
    parser.add_argument("--balkon-groesse", type=int, default=6)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    print(f">>> Oeffne {URL}", file=sys.stderr, flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2_500)

        _try_dismiss_cookies(page)
        page.wait_for_timeout(800)
        _shoot(page, "00_landing")

        # ---- Step 1: Immobilienart ----
        print(">>> Step 1: 'Eigentumswohnung' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Eigentumswohnung", "step1")
        page.wait_for_timeout(2_000)
        _shoot(page, "02_step1_done")

        # ---- Step 2: Adresse ----
        print(">>> Step 2: PLZ + Strasse + Hausnr", file=sys.stderr, flush=True)
        _try_fill_input(page, "PLZ", args.plz, "step2")
        page.wait_for_timeout(1_800)  # Ort-Autobefuellung abwarten
        # Strasse tippen, dann Dropdown abwarten und Item klicken
        _try_fill_input(page, "Straße", args.strasse, "step2")
        page.wait_for_timeout(1_500)
        _click_strasse_dropdown_item(page, args.strasse, args.ort)
        page.wait_for_timeout(500)
        _try_fill_input(page, "Hausnummer", args.hausnr, "step2")
        page.wait_for_timeout(500)
        _shoot(page, "03_step2_filled")

        print(">>> Step 2: 'Weiter' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Weiter", "step2_weiter")
        page.wait_for_timeout(2_000)
        _shoot(page, "04_step2_done")

        # ---- Step 3: Beweggrund ----
        print(">>> Step 3: 'Kauf (Kapitalanlage)' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Kauf (Kapitalanlage)", "step3")
        page.wait_for_timeout(2_000)
        _shoot(page, "05_step3_done")

        # ---- Step 4: Miete ----
        print(">>> Step 4: Miete tippen", file=sys.stderr, flush=True)
        if not _try_fill_input(page, "Monatskaltmiete", args.miete, "step4"):
            _try_fill_input(page, "Miete", args.miete, "step4")
        page.wait_for_timeout(500)
        _shoot(page, "06_step4_filled")

        print(">>> Step 4: 'Weiter' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Weiter", "step4_weiter")
        page.wait_for_timeout(2_500)
        _shoot(page, "07_after_step4_weiter")

        # ---- Step 5: Wohnflaeche + Zimmer ----
        print(">>> Step 5: Wohnflaeche + Zimmer", file=sys.stderr, flush=True)
        _try_fill_input(page, "Wohnfläche", args.wohnflaeche, "step5")
        page.wait_for_timeout(400)
        _try_fill_input(page, "Anzahl der Zimmer", args.zimmer, "step5")
        page.wait_for_timeout(400)
        _shoot(page, "08_step5_filled")
        print(">>> Step 5: 'Weiter' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Weiter", "step5_weiter")
        page.wait_for_timeout(2_500)
        _shoot(page, "09_after_step5_weiter")

        # ---- Step 6: Baujahr ----
        print(">>> Step 6: Baujahr", file=sys.stderr, flush=True)
        _try_fill_input(page, "Baujahr", args.baujahr, "step6")
        page.wait_for_timeout(400)
        _shoot(page, "10_step6_filled")
        print(">>> Step 6: 'Weiter' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Weiter", "step6_weiter")
        page.wait_for_timeout(2_500)
        _shoot(page, "11_after_step6_weiter")

        # ---- Step 7: Sanierung ja/nein (Wizard-Karten, nicht Footer "zufrieden? Ja/Nein") ----
        sanierung_text = "Ja" if args.sanierung == "ja" else "Nein"
        print(f">>> Step 7: Sanierung '{sanierung_text}' klicken (Wizard-Karte)", file=sys.stderr, flush=True)
        clicked = False
        for sel in [
            f'label:has-text("{sanierung_text}"):not(:has-text("zufrieden"))',
            f'[role="radio"]:has-text("{sanierung_text}")',
            f'div:has-text("Sanierung stattgefunden") ~ * >> label:has-text("{sanierung_text}")',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=2_000)
                    print(f">>>   step7: Klick via {sel!r}", file=sys.stderr, flush=True)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            print(">>>   step7: KEIN Sanierungs-Klick moeglich.", file=sys.stderr, flush=True)
        page.wait_for_timeout(1_200)
        _shoot(page, "12_step7_selected")
        # Falls "Ja": inline-Feld "Jahr der letzten Sanierung" erscheint
        if args.sanierung == "ja" and args.sanierungsjahr:
            _try_fill_input(page, "Jahr der letzten Sanierung", args.sanierungsjahr, "step7")
            page.wait_for_timeout(400)
            _shoot(page, "12b_step7_year_filled")
        print(">>> Step 7: 'Weiter' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Weiter", "step7_weiter")
        page.wait_for_timeout(2_500)
        _shoot(page, "13_after_step7_weiter")

        # ---- Step 8: Ausstattung (Auto-Advance) ----
        print(f">>> Step 8: Ausstattung '{args.ausstattung}' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, args.ausstattung, "step8")
        page.wait_for_timeout(2_500)
        _shoot(page, "15_after_step8")

        # ---- Step 9: Weitere Ausstattungsmerkmale (Checkboxen, optional) ----
        print(">>> Step 9: Weitere Ausstattungsmerkmale", file=sys.stderr, flush=True)
        if args.aufzug:
            _try_click_text(page, "Aufzug", "step9_aufzug")
            page.wait_for_timeout(400)
        if args.parkplatz:
            _try_click_text(page, "Parkplatz", "step9_parkplatz")
            page.wait_for_timeout(800)
            _try_fill_input(
                page, "Größe des Parkplatzes",
                str(args.parkplatz_groesse), "step9_parkplatz_size",
            )
            page.wait_for_timeout(400)
        if args.terrasse:
            _try_click_text(page, "Terrasse", "step9_terrasse")
            page.wait_for_timeout(400)
        if args.balkon:
            _try_click_text(page, "Balkon", "step9_balkon")
            page.wait_for_timeout(800)
            _try_fill_input(
                page, "Größe des Balkons",
                str(args.balkon_groesse), "step9_balkon_size",
            )
            page.wait_for_timeout(400)
        _shoot(page, "16_step9_filled")

        print(">>> Step 9: 'Ergebnisse anzeigen' klicken", file=sys.stderr, flush=True)
        _try_click_text(page, "Ergebnisse anzeigen", "step9_submit")
        page.wait_for_timeout(6_000)  # mehr Zeit für Ergebnisseite
        _shoot(page, "17_result_page")

        print(
            ">>> Wizard 1-9 fertig. Browser bleibt offen — Ergebnisseite\n"
            ">>> sollte sichtbar sein. Bitte Screenshot fuer Claude.",
            file=sys.stderr, flush=True,
        )
        try:
            while not page.is_closed():
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
