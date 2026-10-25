"""Vollautonome Marktstatistik-Erhebung fuer Immometrica.

Setzt voraus, dass learned_selectors/immometrica_nodriver_userdata/ existiert.
Klickt selbst durch die 6 Filter-Kombos und sammelt API-Responses.

Workflow pro Geo (PLZ 45357 / Stadt Essen) x Objekt-Typ:
1. Navigiere zu Marktstatistik-Page
2. Setze Zeitraum (H1/2026 = letzter Button)
3. PLZ/Stadt in Ort-Feld eintippen + Autocomplete-Select
4. Objekt-Typ wechseln (ETW / Mietwohnung / Hauskauf+MFH)
5. Statistik erstellen klicken
6. Warten auf Response, Network-Log persistieren
7. Reset Ort-Feld

6 Calls insgesamt:
  - PLZ 45357 / ETW
  - PLZ 45357 / Mietwohnung
  - Essen / ETW
  - Essen / Mietwohnung
  - PLZ 45357 / Hauskauf + Mehrfamilienhaus
  - Essen / Hauskauf + Mehrfamilienhaus

Output:
    runs/<ts>_immometrica_auto_stats_network.json
    runs/<ts>_immometrica_auto_stats_<n>_<label>.png

Lauf:
    .venv\\Scripts\\python.exe inspectors/auto_statistics_immometrica.py
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

URL_STATISTICS = "https://www.immometrica.com/de/statistics"


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _persist_network(network_log: list[dict], path: Path) -> None:
    try:
        path.write_text(
            json.dumps(network_log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f">>> Network-persist FAIL: {e}", file=sys.stderr, flush=True)


async def _save_shot(tab, label: str, ts: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{ts}_immometrica_auto_stats_{label}.png"
    try:
        await tab.save_screenshot(filename=str(p), full_page=False)
        print(f">>> Screenshot: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> Screenshot FAIL ({label}): {e}",
              file=sys.stderr, flush=True)


async def _save_dom_dump(tab, label: str, ts: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{ts}_immometrica_auto_stats_{label}_dom.json"
    try:
        body_text = await tab.evaluate(
            "(document.body && document.body.innerText) || ''"
        )
        # nodriver evaluate gibt CDP-objekt zurueck, wir wollen String
        if isinstance(body_text, dict) and "value" in body_text:
            body_text = body_text["value"]
        url = await tab.evaluate("location.href")
        if isinstance(url, dict) and "value" in url:
            url = url["value"]
        p.write_text(
            json.dumps({"url": url, "body": body_text}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f">>> DOM-Dump: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> DOM-Dump FAIL ({label}): {e}",
              file=sys.stderr, flush=True)


async def main_async() -> int:
    import nodriver as uc
    from nodriver import cdp as cdp_module  # type: ignore

    if not USER_DATA_DIR.exists():
        print(f">>> FATAL: {USER_DATA_DIR} fehlt",
              file=sys.stderr, flush=True)
        return 1

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts()
    net_path = RUNS_DIR / f"{ts}_immometrica_auto_stats_network.json"
    network_log: list[dict] = []

    print(">>> Starte nodriver", file=sys.stderr, flush=True)

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
        tab = await browser.get(URL_STATISTICS)
        await asyncio.sleep(5.0)
        await _save_shot(tab, "01_initial", ts)

        # CDP Network aktivieren — capture ALLES (kein URL-Filter, JSON-only)
        try:
            await tab.send(cdp_module.network.enable())
        except Exception as e:
            print(f">>> Network.enable FAIL: {e}", file=sys.stderr, flush=True)

        async def _on_response(event):
            try:
                resp = event.response
                url = resp.url or ""
                ct = (resp.headers or {}).get("content-type", "") if resp.headers else ""
                # Wir wollen JSON-Responses ODER alles unter /de/statistics
                wanted = (
                    "json" in ct.lower()
                    or "/de/statistics" in url
                    or "/api/" in url
                )
                if not wanted:
                    return
                body = ""
                try:
                    body_resp = await tab.send(
                        cdp_module.network.get_response_body(event.request_id)
                    )
                    body_val = body_resp[0] if isinstance(body_resp, tuple) else body_resp
                    if isinstance(body_val, str):
                        body = body_val[:20000]
                except Exception:
                    pass
                entry = {
                    "ts": _ts(),
                    "status": resp.status,
                    "url": url[:500],
                    "content_type": ct[:120],
                    "body": body,
                }
                network_log.append(entry)
                # Persist sofort
                _persist_network(network_log, net_path)
            except Exception:
                pass

        try:
            tab.add_handler(cdp_module.network.ResponseReceived, _on_response)
            print(">>> Response-Handler aktiv", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Handler-Reg FAIL: {e}", file=sys.stderr, flush=True)

        # Bestimme letzten Zeitraum-Button-Text (z.B. H1/2026)
        try:
            buttons_text = await tab.evaluate(
                """JSON.stringify(
                    Array.from(document.querySelectorAll('a, button'))
                    .map(b => b.innerText.trim())
                    .filter(t => /^H[12]\\/\\d{4}$/.test(t))
                )"""
            )
            print(f">>> Halbjahr-Buttons: {buttons_text}",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Halbjahr-Suche FAIL: {e}",
                  file=sys.stderr, flush=True)

        # 6 Filter-Kombos durchlaufen
        configs = [
            {"label": "1_plz_etw_kauf", "geo": "45357",
             "type_radio": "ETW", "mfh": False},
            {"label": "2_plz_etw_miete", "geo": "45357",
             "type_radio": "Mietwohnung", "mfh": False},
            {"label": "3_essen_etw_kauf", "geo": "Essen",
             "type_radio": "ETW", "mfh": False},
            {"label": "4_essen_etw_miete", "geo": "Essen",
             "type_radio": "Mietwohnung", "mfh": False},
            {"label": "5_plz_hauskauf_mfh", "geo": "45357",
             "type_radio": "Hauskauf", "mfh": True},
            {"label": "6_essen_hauskauf_mfh", "geo": "Essen",
             "type_radio": "Hauskauf", "mfh": True},
        ]

        for cfg in configs:
            print(f">>> === Config: {cfg['label']} ===",
                  file=sys.stderr, flush=True)

            # Frische Page laden
            await tab.get(URL_STATISTICS)
            await asyncio.sleep(4.0)

            # Letzter Halbjahres-Button klicken (H1/2026 oder H2/2026)
            try:
                clicked_period = await tab.evaluate(
                    """(() => {
                        const btns = Array.from(document.querySelectorAll('a, button'))
                            .filter(b => /^H[12]\\/\\d{4}$/.test(b.innerText.trim()));
                        if (btns.length === 0) return null;
                        const last = btns[btns.length - 1];
                        last.click();
                        return last.innerText.trim();
                    })()"""
                )
                if isinstance(clicked_period, dict) and "value" in clicked_period:
                    clicked_period = clicked_period["value"]
                print(f">>>   Zeitraum: {clicked_period}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f">>>   Zeitraum-Click FAIL: {e}",
                      file=sys.stderr, flush=True)

            # Objekt-Typ-Radio klicken
            try:
                radio_clicked = await tab.evaluate(
                    f"""(() => {{
                        const labels = Array.from(document.querySelectorAll('label, div'))
                            .filter(el => el.innerText.trim() === {json.dumps(cfg['type_radio'])});
                        for (const l of labels) {{
                            const r = l.querySelector('input[type="radio"]')
                                || l.previousElementSibling && l.previousElementSibling.querySelector
                                ? l.previousElementSibling : null;
                            if (r && r.click) {{ r.click(); return true; }}
                        }}
                        // Alternativ: input[type=radio] mit Label-Text via 'for'
                        const inputs = Array.from(document.querySelectorAll('input[type="radio"]'));
                        for (const inp of inputs) {{
                            const lbl = inp.parentElement.innerText.trim();
                            if (lbl.includes({json.dumps(cfg['type_radio'])})) {{
                                inp.click(); return true;
                            }}
                        }}
                        return false;
                    }})()"""
                )
                if isinstance(radio_clicked, dict) and "value" in radio_clicked:
                    radio_clicked = radio_clicked["value"]
                print(f">>>   Radio {cfg['type_radio']}: {radio_clicked}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f">>>   Radio-Click FAIL: {e}",
                      file=sys.stderr, flush=True)

            # Ort-Eingabe
            try:
                ort_input = await tab.query_selector(
                    'input[placeholder*="Ort" i]'
                )
                if not ort_input:
                    ort_input = await tab.query_selector(
                        'input[placeholder*="PLZ" i]'
                    )
                if ort_input:
                    await ort_input.click()
                    await asyncio.sleep(0.3)
                    await ort_input.send_keys(cfg["geo"])
                    await asyncio.sleep(2.0)  # Autocomplete warten
                    # Pfeil-runter + Enter zur Auswahl
                    await tab.send_keys("ArrowDown")
                    await asyncio.sleep(0.3)
                    await tab.send_keys("Enter")
                    await asyncio.sleep(1.5)
                    print(f">>>   Ort {cfg['geo']!r} via Autocomplete",
                          file=sys.stderr, flush=True)
                else:
                    print(">>>   Ort-Feld nicht gefunden",
                          file=sys.stderr, flush=True)
            except Exception as e:
                print(f">>>   Ort-Eingabe FAIL: {e}",
                      file=sys.stderr, flush=True)

            # MFH-Checkbox (bei Hauskauf)
            if cfg["mfh"]:
                try:
                    mfh_clicked = await tab.evaluate(
                        """(() => {
                            const labels = Array.from(document.querySelectorAll('label, div'))
                                .filter(el => el.innerText.trim() === 'Mehrfamilienhaus');
                            for (const l of labels) {
                                const cb = l.querySelector('input[type="checkbox"]');
                                if (cb) { cb.click(); return true; }
                                if (l.previousElementSibling
                                    && l.previousElementSibling.type === 'checkbox') {
                                    l.previousElementSibling.click();
                                    return true;
                                }
                            }
                            const cbs = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                            for (const cb of cbs) {
                                const lbl = cb.parentElement.innerText.trim();
                                if (lbl.includes('Mehrfamilienhaus')) {
                                    cb.click(); return true;
                                }
                            }
                            return false;
                        })()"""
                    )
                    if isinstance(mfh_clicked, dict) and "value" in mfh_clicked:
                        mfh_clicked = mfh_clicked["value"]
                    print(f">>>   MFH-Checkbox: {mfh_clicked}",
                          file=sys.stderr, flush=True)
                    await asyncio.sleep(1.0)
                except Exception as e:
                    print(f">>>   MFH-Click FAIL: {e}",
                          file=sys.stderr, flush=True)

            # "Statistik erstellen" klicken
            try:
                stat_clicked = await tab.evaluate(
                    """(() => {
                        const btns = Array.from(document.querySelectorAll('button, a'))
                            .filter(b => b.innerText.trim() === 'Statistik erstellen');
                        if (btns.length === 0) return false;
                        btns[0].click();
                        return true;
                    })()"""
                )
                if isinstance(stat_clicked, dict) and "value" in stat_clicked:
                    stat_clicked = stat_clicked["value"]
                print(f">>>   Statistik-Click: {stat_clicked}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(8.0)  # Response abwarten
            except Exception as e:
                print(f">>>   Statistik-Click FAIL: {e}",
                      file=sys.stderr, flush=True)

            # DOM-Dump + Screenshot fuer Verifikation
            await _save_shot(tab, cfg["label"], ts)
            await _save_dom_dump(tab, cfg["label"], ts)

            # Persistieren
            _persist_network(network_log, net_path)
            print(f">>>   Network-Log: {len(network_log)} Calls",
                  file=sys.stderr, flush=True)

        print(f">>> FERTIG. Total Network-Calls: {len(network_log)}",
              file=sys.stderr, flush=True)
        print(f">>> Network-Log: {net_path}",
              file=sys.stderr, flush=True)
        return 0

    except Exception as e:
        print(f">>> Exception: {e}\n{traceback.format_exc()}",
              file=sys.stderr, flush=True)
        _persist_network(network_log, net_path)
        return 99
    finally:
        try:
            _persist_network(network_log, net_path)
        except Exception:
            pass
        try:
            browser.stop()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    import nodriver as uc
    return uc.loop().run_until_complete(main_async())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
