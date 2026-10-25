"""Phase-B-Skript: Adress-Suche auf Immometrica + Network-Sniffer.

Setzt voraus, dass `inspectors/login_immometrica_autonomous.py` bereits
gelaufen ist und Cookies in `learned_selectors/immometrica_nodriver_userdata/`
persistiert sind. Re-Login wird vermieden — direkter Sprung zur Such-Page.

Strategie:
1. Persistent Context laden (Cookies sind da)
2. Suche-Page oeffnen (vermutlich /de/home oder /de/search)
3. Adresse eingeben (Prosperstraße 59, 45357 Essen)
4. Network-Sniffer protokolliert alle JSON-Responses
5. Screenshots an jedem Schritt
6. Ergebnis-Page DOM dumpen
7. Final-Report: gefundene API-Endpoints + Werte (Marktwert/Miete/Rendite)

Lauf:
    .venv\\Scripts\\python.exe inspectors/sniff_immometrica_search.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
RUNS_DIR = PROJ_ROOT / "runs"
STATE_DIR = PROJ_ROOT / "learned_selectors"
USER_DATA_DIR = STATE_DIR / "immometrica_nodriver_userdata"
BERLIN_TZ = timezone(timedelta(hours=2))

URL_HOME_AUTH = "https://www.immometrica.com/de/home"
SEARCH_ADDR = "Prosperstraße 59, 45357 Essen"


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


async def _save_shot(tab, slug: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{_ts()}_immometrica_search_{slug}.png"
    try:
        await tab.save_screenshot(filename=str(p), full_page=False)
        print(f">>> Screenshot: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> Screenshot FAIL ({slug}): {e}", file=sys.stderr, flush=True)


async def _save_dom(tab, slug: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{_ts()}_immometrica_search_{slug}_dom.json"
    try:
        dom = await tab.evaluate(
            """({
                url: location.href,
                title: document.title,
                headings: Array.from(document.querySelectorAll('h1,h2,h3'))
                    .map(h => (h.innerText || '').trim()).filter(Boolean).slice(0, 30),
                inputs: Array.from(document.querySelectorAll('input,textarea')).map(e => ({
                    type: e.type, name: e.name, id: e.id,
                    placeholder: e.placeholder || null,
                    ariaLabel: e.getAttribute('aria-label'),
                    visible: e.offsetParent !== null,
                })),
                buttons: Array.from(document.querySelectorAll('button')).map(e => ({
                    text: (e.innerText || '').trim().slice(0, 80),
                    type: e.type,
                    ariaLabel: e.getAttribute('aria-label'),
                    visible: e.offsetParent !== null,
                })).filter(b => b.text || b.ariaLabel),
                body_text: (document.body && document.body.innerText
                    ? document.body.innerText.slice(0, 5000) : '')
            })"""
        )
        p.write_text(json.dumps(dom, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f">>> DOM-Dump: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> DOM-Dump FAIL ({slug}): {e}",
              file=sys.stderr, flush=True)


async def main_async() -> int:
    import nodriver as uc

    if not USER_DATA_DIR.exists():
        print(f">>> FATAL: {USER_DATA_DIR} fehlt. Erst login_immometrica_autonomous.py laufen lassen.",
              file=sys.stderr, flush=True)
        return 1

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    network_log: list[dict] = []

    print(">>> Starte nodriver mit persistierten Cookies",
          file=sys.stderr, flush=True)

    browser = await uc.start(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        lang="de-DE",
        browser_args=[
            "--lang=de-DE",
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
    )

    try:
        # Network-Sniffer setup (via CDP)
        # nodriver hat keine direkte page.on('response') Schnittstelle wie Playwright,
        # aber wir koennen Network-Domain aktivieren und Events abonnieren.
        from nodriver import cdp as cdp_module  # type: ignore

        tab = await browser.get(URL_HOME_AUTH)
        await asyncio.sleep(4.0)

        # CDP Network-Domain aktivieren
        try:
            await tab.send(cdp_module.network.enable())
            print(">>> CDP Network-Domain aktiviert", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> CDP Network.enable FAIL: {e}",
                  file=sys.stderr, flush=True)

        # Sniffer-Handler registrieren — capture JSON-Responses
        try:
            async def _on_response_received(event):
                try:
                    resp = event.response
                    url = resp.url
                    if "immometrica" not in url:
                        return
                    ct = resp.headers.get("content-type", "") if resp.headers else ""
                    is_json = "json" in ct.lower() or "/api/" in url
                    is_html_doc = "html" in ct.lower()
                    if not (is_json or "/api/" in url):
                        return
                    body_snippet = ""
                    try:
                        body_resp = await tab.send(
                            cdp_module.network.get_response_body(event.request_id)
                        )
                        body = body_resp[0] if isinstance(body_resp, tuple) else body_resp
                        if isinstance(body, str):
                            body_snippet = body[:5000]
                    except Exception:
                        pass
                    network_log.append({
                        "status": resp.status,
                        "url": url[:400],
                        "content_type": ct[:100],
                        "body_snippet": body_snippet,
                    })
                except Exception:
                    pass

            tab.add_handler(
                cdp_module.network.ResponseReceived, _on_response_received
            )
            print(">>> Response-Handler registriert",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Handler-Reg FAIL: {e}", file=sys.stderr, flush=True)

        # Snapshot der Home-Page
        print(f">>> Aktuelle URL: {tab.url}", file=sys.stderr, flush=True)
        await _save_shot(tab, "01_home_auth")
        await _save_dom(tab, "01_home_auth")

        # Navigiere zu "Neue Suche" (Adress-Filter-Pfad).
        # Wertbericht ist ein Sprengnetter-Wizard (kostet evtl. extra).
        print(">>> Step Nav: 'Neue Suche' im Menue klicken",
              file=sys.stderr, flush=True)
        nav_clicked = False
        for nav_text in ["Neue Suche", "Letzte Suche", "Wertbericht"]:
            try:
                elem = await tab.find(text=nav_text, best_match=True, timeout=3)
                if elem:
                    await elem.click()
                    nav_clicked = True
                    print(f">>>   Nav via {nav_text!r}",
                          file=sys.stderr, flush=True)
                    await asyncio.sleep(4.0)
                    break
            except Exception as e:
                print(f">>>   Nav-Try {nav_text!r} FAIL: {e}",
                      file=sys.stderr, flush=True)
                continue
        if not nav_clicked:
            print(">>>   FAIL: Nav nicht moeglich",
                  file=sys.stderr, flush=True)
            await _save_shot(tab, "01b_no_nav")
            return 2
        await _save_shot(tab, "01c_after_nav")
        await _save_dom(tab, "01c_after_nav")
        try:
            print(f">>>   URL nach Nav: {tab.url}",
                  file=sys.stderr, flush=True)
        except Exception:
            pass

        # Suche-Eingabefeld finden
        print(">>> Suche-Eingabefeld finden", file=sys.stderr, flush=True)
        search_input = None
        for sel in [
            'input[type="search"]',
            'input[placeholder*="Adresse" i]',
            'input[placeholder*="Straße" i]',
            'input[placeholder*="Ort" i]',
            'input[placeholder*="Suche" i]',
            'input[name*="search" i]',
            'input[name*="address" i]',
            'input[name*="strasse" i]',
            'input[autocomplete*="address" i]',
            'input[type="text"]:not([name="csrfmiddlewaretoken"])',
        ]:
            try:
                elem = await tab.query_selector(sel)
                if elem:
                    search_input = elem
                    print(f">>>   Eingabe-Feld via {sel}",
                          file=sys.stderr, flush=True)
                    break
            except Exception:
                continue
        if search_input is None:
            print(">>>   FAIL: kein Eingabe-Feld gefunden",
                  file=sys.stderr, flush=True)
            await _save_shot(tab, "02_no_search_input")
            await _save_dom(tab, "02_no_search_input")
            return 2

        # Adresse tippen
        print(f">>> Adresse tippen: {SEARCH_ADDR!r}",
              file=sys.stderr, flush=True)
        await search_input.click()
        await asyncio.sleep(0.5)
        # nodriver send_keys ist robust gegen Special-Chars
        await search_input.send_keys(SEARCH_ADDR)
        await asyncio.sleep(3.0)  # warten auf Autocomplete
        await _save_shot(tab, "02_address_typed")
        await _save_dom(tab, "02_address_typed")

        # ArrowDown + Enter (Autocomplete-Standardpattern)
        try:
            await tab.send_keys("ArrowDown")
            await asyncio.sleep(0.5)
            await tab.send_keys("Enter")
            print(">>> ArrowDown+Enter zum Autocomplete-Auswahl",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>>   Autocomplete-Auswahl FAIL: {e}",
                  file=sys.stderr, flush=True)
        await asyncio.sleep(7.0)  # warten auf Result-Load
        await _save_shot(tab, "03_after_search")
        await _save_dom(tab, "03_after_search")

        # Falls Adresse als Suggestion erschienen ist, aber keine
        # weitere Aktion: nochmal Enter
        try:
            await tab.send_keys("Enter")
            await asyncio.sleep(5.0)
            await _save_shot(tab, "04_after_second_enter")
            await _save_dom(tab, "04_after_second_enter")
        except Exception:
            pass

        # Schliess Network-Log
        try:
            net_path = RUNS_DIR / f"{_ts()}_immometrica_search_network.json"
            net_path.write_text(
                json.dumps(network_log, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(
                f">>> Network-Log: {net_path.name} ({len(network_log)} Eintraege)",
                file=sys.stderr, flush=True,
            )
        except Exception as e:
            print(f">>> Network-Log FAIL: {e}", file=sys.stderr, flush=True)

        # Print URLs der relevantesten Calls
        print(">>> Relevante Network-Calls:", file=sys.stderr, flush=True)
        for e in network_log[-30:]:
            print(f">>>   [{e['status']}] {e['url'][:160]}",
                  file=sys.stderr, flush=True)

        return 0

    except Exception as e:
        print(f">>> Exception: {e}\n{traceback.format_exc()}",
              file=sys.stderr, flush=True)
        return 99
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    import nodriver as uc
    return uc.loop().run_until_complete(main_async())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
