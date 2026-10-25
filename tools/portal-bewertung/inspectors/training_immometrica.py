"""Training-Skript: Browser offen halten, User klickt manuell, Skript loggt.

Setzt voraus, dass `learned_selectors/immometrica_nodriver_userdata/` existiert
(d.h. einmaliger Login bereits durchgefuehrt).

Strategie:
- nodriver-Browser mit persistierten Cookies starten
- CDP Network-Domain aktivieren, ResponseReceived abonnieren
- Alle 5s: URL-Snapshot + Network-Log-Stand persistent loggen
- Browser bleibt offen bis User ihn schliesst
- Beim Schliessen: Vollstaendiges Network-Log exportieren

User-Aufgabe waehrend des Skripts laeuft:
1. Pfad 1: Marktpreis + Marktmiete fuer Adresse (Prosperstr. 59) klicken
2. Pfad 2: Markt-Statistiken fuer dieselbe Adresse klicken
3. Browser-Fenster schliessen

Output:
    runs/<ts>_immometrica_training_urls.log         (URL-Verlauf)
    runs/<ts>_immometrica_training_network.json     (alle JSON-Responses)
    runs/<ts>_immometrica_training_<n>_step.png     (Screenshots periodisch)

Lauf:
    .venv\\Scripts\\python.exe inspectors/training_immometrica.py
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

# Network-Sniffer Filter: nur Calls die uns interessieren
INTERESTING_URL_PARTS = (
    "/api/", "/search", "/object", "/marktwert", "/preis",
    "/miete", "/rendite", "/statistik", "/report", "/avm",
    "/details", "/data", "/lage", "/adress", "/geo", "/lookup",
    "/valuation", "/property", "/listing",
)


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


async def main_async() -> int:
    import nodriver as uc
    from nodriver import cdp as cdp_module  # type: ignore

    if not USER_DATA_DIR.exists():
        print(f">>> FATAL: {USER_DATA_DIR} fehlt — erst login_immometrica_autonomous.py laufen lassen.",
              file=sys.stderr, flush=True)
        return 1

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    log_path = RUNS_DIR / f"{ts}_immometrica_training_urls.log"
    net_path = RUNS_DIR / f"{ts}_immometrica_training_network.json"
    network_log: list[dict] = []
    log_lines: list[str] = [f"=== Training-Session {ts} ===\n"]

    print(">>> Starte Browser (nodriver, persistierte Cookies)",
          file=sys.stderr, flush=True)
    print(f">>> URL-Log: {log_path.name}",
          file=sys.stderr, flush=True)
    print(f">>> Network-Log: {net_path.name}",
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
        tab = await browser.get(URL_HOME_AUTH)
        await asyncio.sleep(4.0)

        # CDP Network aktivieren
        try:
            await tab.send(cdp_module.network.enable())
            print(">>> CDP Network aktiv", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Network.enable FAIL: {e}",
                  file=sys.stderr, flush=True)

        # Response-Handler
        async def _on_response_received(event):
            try:
                resp = event.response
                url = resp.url
                if "immometrica" not in url and "sprengnetter" not in url:
                    return
                ct = (resp.headers or {}).get("content-type", "")
                is_json = "json" in ct.lower()
                is_interesting = any(p in url.lower() for p in INTERESTING_URL_PARTS)
                if not (is_json or is_interesting):
                    return
                body_snippet = ""
                try:
                    body_resp = await tab.send(
                        cdp_module.network.get_response_body(event.request_id)
                    )
                    body = body_resp[0] if isinstance(body_resp, tuple) else body_resp
                    if isinstance(body, str):
                        body_snippet = body[:8000]
                except Exception:
                    pass
                entry = {
                    "ts": _ts(),
                    "status": resp.status,
                    "method": getattr(event, "type_", None),
                    "url": url[:400],
                    "content_type": ct[:100],
                    "body_snippet": body_snippet,
                }
                network_log.append(entry)
                # Optional: live print für interessante Calls
                if is_interesting:
                    print(f">>>   [{resp.status}] {url[:140]}",
                          file=sys.stderr, flush=True)
            except Exception:
                pass

        try:
            tab.add_handler(
                cdp_module.network.ResponseReceived, _on_response_received
            )
            print(">>> Response-Handler aktiv", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Handler-Reg FAIL: {e}", file=sys.stderr, flush=True)

        print(">>> Browser bleibt offen. Klicke jetzt im Browser:")
        print(">>>   1. Marktpreis + Marktmiete fuer Prosperstr. 59 oeffnen")
        print(">>>   2. Markt-Statistiken fuer dieselbe Adresse oeffnen")
        print(">>>   3. Browser-Fenster schliessen, wenn du fertig bist")
        print(">>> Skript loggt URL-Aenderungen + alle JSON-Responses.")
        sys.stderr.flush()

        last_url = ""
        last_net_count = 0
        iter_count = 0
        log_path.write_text("".join(log_lines), encoding="utf-8")

        while True:
            iter_count += 1
            try:
                url_now = tab.url or ""
            except Exception:
                # Browser geschlossen
                print(">>> Tab nicht mehr erreichbar — beende.",
                      file=sys.stderr, flush=True)
                break
            if not url_now:
                # Browser-Tab evtl. weg
                print(">>> Tab leer — beende.",
                      file=sys.stderr, flush=True)
                break
            if url_now != last_url:
                log_lines.append(f"[{_ts()}] URL: {url_now}\n")
                last_url = url_now
                log_path.write_text("".join(log_lines), encoding="utf-8")

            net_now = len(network_log)
            if net_now > last_net_count:
                log_lines.append(
                    f"[{_ts()}] Netzwerk: +{net_now - last_net_count} Calls "
                    f"(Total {net_now})\n"
                )
                last_net_count = net_now
                log_path.write_text("".join(log_lines), encoding="utf-8")

            # Network-Log periodisch persistieren
            if iter_count % 6 == 0:
                try:
                    net_path.write_text(
                        json.dumps(network_log, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception:
                    pass

            # Periodischer Screenshot, ca. alle 30s
            if iter_count % 6 == 1:
                try:
                    shot = RUNS_DIR / f"{ts}_immometrica_training_step{iter_count:03d}.png"
                    await tab.save_screenshot(filename=str(shot), full_page=False)
                except Exception:
                    pass

            await asyncio.sleep(5.0)

        # Final-Persist
        try:
            net_path.write_text(
                json.dumps(network_log, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f">>> Final Network-Log: {net_path.name} ({len(network_log)} Calls)",
                  file=sys.stderr, flush=True)
        except Exception:
            pass
        try:
            log_path.write_text("".join(log_lines), encoding="utf-8")
        except Exception:
            pass

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
