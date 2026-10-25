"""Aufzeichner fuer Browser-Storage-State (Cookies + localStorage).

Oeffnet eine URL im sichtbaren Browser. User klickt manuell Cookie-
Consent. Das Skript erkennt automatisch den Cookie-Spike (Sourcepoint/
DSGVO-Cookies werden gesetzt) und speichert dann den Storage-State nach
OUTFILE.

Lauf:
    .venv\\Scripts\\python.exe inspectors/record_state.py \\
        https://www.immobilienscout24.de/immobilie-bewerten/ \\
        learned_selectors/immoscout24_state.json
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Zeichnet Browser-Storage-State auf, "
        "sobald der User Cookie-Consent gegeben hat."
    )
    parser.add_argument("url")
    parser.add_argument(
        "outfile",
        type=Path,
        help="Pfad fuer den Storage-State (JSON).",
    )
    parser.add_argument(
        "--cookie-spike-threshold", type=int, default=8,
        help="Anzahl Cookies, ab der wir den State als 'akzeptiert' werten "
             "(IS24 setzt typischerweise 30+ Cookies nach Consent).",
    )
    parser.add_argument("--max-wait-s", type=int, default=180)
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    args.outfile.parent.mkdir(parents=True, exist_ok=True)

    print(f">>> Oeffne {args.url} (headed)", file=sys.stderr, flush=True)
    print(
        ">>> Klicke 'Alle akzeptieren' im Cookie-Banner. "
        "Das Skript erkennt das automatisch und speichert dann.",
        file=sys.stderr, flush=True,
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)

        initial_cookies = len(ctx.cookies())
        print(
            f">>> Initial-Cookies: {initial_cookies}. "
            f"Warte auf Spike >= {args.cookie_spike_threshold}.",
            file=sys.stderr, flush=True,
        )

        deadline = time.monotonic() + args.max_wait_s
        last_log = 0
        while time.monotonic() < deadline:
            try:
                cookies_now = len(ctx.cookies())
            except Exception:
                cookies_now = -1

            now = time.monotonic()
            if now - last_log > 5:
                print(f">>>   Cookies aktuell: {cookies_now}",
                      file=sys.stderr, flush=True)
                last_log = now

            if cookies_now >= args.cookie_spike_threshold:
                print(
                    f">>> Cookie-Spike erkannt ({cookies_now} >= "
                    f"{args.cookie_spike_threshold}). Speichere State.",
                    file=sys.stderr, flush=True,
                )
                # Kurz noch warten, damit alle Consent-Cookies gesetzt sind
                page.wait_for_timeout(2_000)
                break
            time.sleep(2)
        else:
            print(
                f">>> Timeout nach {args.max_wait_s}s — kein Consent erkannt. "
                "Speichere trotzdem den aktuellen State.",
                file=sys.stderr, flush=True,
            )

        try:
            ctx.storage_state(path=str(args.outfile))
            size = args.outfile.stat().st_size
            print(
                f">>> Storage-State gespeichert: {args.outfile} ({size} bytes)",
                file=sys.stderr, flush=True,
            )
        except Exception as e:
            print(f">>> Storage-State FAIL: {e}", file=sys.stderr, flush=True)

        try:
            browser.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
