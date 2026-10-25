"""Probe: Geo-Eingabe in React-Select mit grosszuegigen Delays.

Zeigt: erscheinen Suggestions nach Tippen? Wie sehen sie aus?
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
RUNS_DIR = PROJ_ROOT / "runs"
USER_DATA_DIR = PROJ_ROOT / "learned_selectors" / "immometrica_nodriver_userdata"


async def main_async() -> int:
    import nodriver as uc

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
        tab = await browser.get("https://www.immometrica.com/de/statistics")
        await asyncio.sleep(6.0)

        # Step 1: Existing Trash-Tags loeschen
        await tab.evaluate(
            """(() => {
                const widget = document.querySelector('.location-select-widget');
                if (!widget) return;
                const trashes = widget.querySelectorAll('a > i.fa-trash, a > i.fas.fa-trash');
                for (const ico of trashes) {
                    const a = ico.closest('a');
                    if (a) a.click();
                }
            })()"""
        )
        await asyncio.sleep(2.0)
        print(f">>> Nach Trash-Click", file=sys.stderr, flush=True)
        await tab.save_screenshot(filename=str(RUNS_DIR / "probe_geo_01_after_trash.png"))

        # Step 2: location-toggle clicken um React-Select zu oeffnen
        await tab.evaluate(
            """(() => {
                const widget = document.querySelector('.location-select-widget');
                if (!widget) return;
                const toggle = widget.querySelector('.location-toggle');
                if (toggle) toggle.click();
            })()"""
        )
        await asyncio.sleep(2.0)
        await tab.save_screenshot(filename=str(RUNS_DIR / "probe_geo_02_toggle.png"))

        # Step 3: React-Select Input fokussieren + tippen
        inp = await tab.query_selector('input[id^="react-select-"][id$="-input"]')
        if not inp:
            print(">>> Kein react-select Input gefunden", file=sys.stderr, flush=True)
            return 1
        await inp.click()
        await asyncio.sleep(1.0)

        # Native send_keys, char-by-char mit grosseren Delays (300ms)
        query = "45357"
        for i, ch in enumerate(query):
            await inp.send_keys(ch)
            await asyncio.sleep(0.3)
            # Nach jedem Char: pruefe ob Suggestions da sind
            n_opts = await tab.evaluate(
                """(() => {
                    return document.querySelectorAll(
                        '[id^="react-select-"][id*="-option"]'
                    ).length;
                })()"""
            )
            if isinstance(n_opts, dict) and "value" in n_opts:
                n_opts = n_opts["value"]
            print(f">>> Nach Char {i+1}/{len(query)} ('{query[:i+1]}'): {n_opts} Suggestions",
                  file=sys.stderr, flush=True)

        # Längere Wartezeit
        await asyncio.sleep(4.0)
        await tab.save_screenshot(filename=str(RUNS_DIR / "probe_geo_03_typed.png"))

        # Dump aller Suggestion-Optionen + IDs
        opts_dump = await tab.evaluate(
            """JSON.stringify(
                Array.from(document.querySelectorAll(
                    '[id^="react-select-"][id*="-option"]'
                )).map(o => ({
                    id: o.id,
                    text: (o.innerText||'').trim(),
                    visible: o.offsetParent !== null,
                    classList: Array.from(o.classList),
                }))
            )"""
        )
        if isinstance(opts_dump, dict) and "value" in opts_dump:
            opts_dump = opts_dump["value"]
        print(f">>> Options Dump: {opts_dump}", file=sys.stderr, flush=True)

        # Click auf erstes passendes
        picked = await tab.evaluate(
            """(() => {
                const opts = Array.from(document.querySelectorAll(
                    '[id^="react-select-"][id*="-option"]'
                )).filter(o => o.offsetParent !== null);
                if (opts.length === 0) return null;
                const target = opts[0];
                if (!target.id) target.id = 'probe-target-' + Date.now();
                return target.id;
            })()"""
        )
        if isinstance(picked, dict) and "value" in picked:
            picked = picked["value"]
        if picked:
            opt = await tab.query_selector(f'#{picked}')
            if opt:
                await opt.click()
                print(f">>> Native click on option {picked}",
                      file=sys.stderr, flush=True)
        else:
            print(">>> Keine sichtbare Suggestion zum Klicken",
                  file=sys.stderr, flush=True)

        await asyncio.sleep(3.0)
        await tab.save_screenshot(filename=str(RUNS_DIR / "probe_geo_04_after_pick.png"))

        # State pruefen
        body = await tab.evaluate("(document.body && document.body.innerText) || ''")
        if isinstance(body, dict) and "value" in body:
            body = body["value"]
        # Suche "Im Baum auswählen\n<TAG>\n"
        import re
        m = re.search(r'Im Baum auswählen\s*\n\s*([^\n]+?)\s*\n', body)
        if m:
            print(f">>> Ort-Tag-State: {m.group(1)!r}",
                  file=sys.stderr, flush=True)
        else:
            print(">>> Ort-Tag-State nicht parsbar", file=sys.stderr, flush=True)

        return 0
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def main() -> int:
    import nodriver as uc
    return uc.loop().run_until_complete(main_async())


if __name__ == "__main__":
    sys.exit(main())
