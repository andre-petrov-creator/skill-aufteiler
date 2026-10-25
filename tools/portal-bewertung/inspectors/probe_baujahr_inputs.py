# -*- coding: utf-8 -*-
"""Probe: Baujahr-Inputs direkt testen + Bauliches-Tab-Status pruefen.

Sequenz minimal:
  1. tab.get(URL_HOME) + 8s
  2. Sidebar-Klick auf Marktstatistik + 10s
  3. Direkte JS-Inspection: gibt es id_construction_year_0/1?
  4. _click_bauliches_tab + 2s
  5. Direkter JS-Set + Read der Inputs
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
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from portals.immometrica.portal import (
    URL_HOME,
    USER_DATA_DIR,
    _click_bauliches_tab,
    _click_marktstatistik_sidebar,
)


async def main_async() -> int:
    import nodriver as uc

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

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
        tab = await browser.get(URL_HOME)
        await asyncio.sleep(8.0)

        await _click_marktstatistik_sidebar(tab)
        await asyncio.sleep(10.0)

        # Phase 1: Inputs direkt im DOM finden (auch ohne Tab-Wechsel)?
        r = await tab.evaluate(
            """JSON.stringify({
                construction_year_0: !!document.getElementById('id_construction_year_0'),
                construction_year_1: !!document.getElementById('id_construction_year_1'),
                num_inputs: document.querySelectorAll('input').length,
                num_baujahr_labels: Array.from(document.querySelectorAll('label'))
                    .filter(l => /baujahr/i.test(l.innerText)).length,
                tabs_in_dom: Array.from(document.querySelectorAll('a,button,li'))
                    .filter(e => /^(Start|Bauliches|Weiteres|Cashflow)$/.test(e.innerText.trim()))
                    .map(e => ({txt: e.innerText.trim(), tag: e.tagName,
                                cls: e.className.slice(0,80)}))
            })"""
        )
        if isinstance(r, dict) and "value" in r:
            r = r["value"]
        print(f">>> Phase 1 (vor Tab-Klick): {r}", file=sys.stderr, flush=True)

        # Phase 2: Bauliches-Tab klicken
        bt_ok = await _click_bauliches_tab(tab)
        print(f">>> Bauliches-Tab-Klick: {bt_ok}", file=sys.stderr, flush=True)
        await asyncio.sleep(3.0)

        r2 = await tab.evaluate(
            """JSON.stringify({
                construction_year_0: !!document.getElementById('id_construction_year_0'),
                construction_year_1: !!document.getElementById('id_construction_year_1'),
                offsetParent_0: (document.getElementById('id_construction_year_0') || {}).offsetParent !== null,
                offsetParent_1: (document.getElementById('id_construction_year_1') || {}).offsetParent !== null,
                val_0: (document.getElementById('id_construction_year_0') || {}).value,
                val_1: (document.getElementById('id_construction_year_1') || {}).value
            })"""
        )
        if isinstance(r2, dict) and "value" in r2:
            r2 = r2["value"]
        print(f">>> Phase 2 (nach Bauliches-Klick): {r2}", file=sys.stderr, flush=True)

        # Phase 3: Direkt setzen via Native-Setter
        r3 = await tab.evaluate(
            """(() => {
                const inp0 = document.getElementById('id_construction_year_0');
                const inp1 = document.getElementById('id_construction_year_1');
                if (!inp0 || !inp1) return JSON.stringify({err: 'inputs nicht da'});
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(inp0, '1900');
                inp0.dispatchEvent(new Event('input', {bubbles: true}));
                inp0.dispatchEvent(new Event('change', {bubbles: true}));
                setter.call(inp1, '1980');
                inp1.dispatchEvent(new Event('input', {bubbles: true}));
                inp1.dispatchEvent(new Event('change', {bubbles: true}));
                return JSON.stringify({val_0: inp0.value, val_1: inp1.value});
            })()"""
        )
        if isinstance(r3, dict) and "value" in r3:
            r3 = r3["value"]
        print(f">>> Phase 3 (nach Set): {r3}", file=sys.stderr, flush=True)

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
