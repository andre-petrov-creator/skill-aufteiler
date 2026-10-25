# -*- coding: utf-8 -*-
"""Diagnose: 1 Config submitten + kompletten DOM dumpen.

Ziel: alle 9 Tabellen identifizieren, die Immometrica auf der Marktstatistik
nach 'Statistik erstellen' rendert. Output: runs/<ts>_full_dom.txt mit
body.innerText, plus runs/<ts>_full_dom.html mit document.documentElement.outerHTML.

Sequence:
  1. tab.get(URL_HOME) + 8s
  2. Login-Check (Auto-Login Fallback)
  3. _click_marktstatistik_sidebar + 8s
  4. _enter_geo("45357", "45357") + Enter
  5. _select_period("latest")
  6. _click_bauliches_tab + _set_baujahr_range(1900, 1980)
  7. _uncheck_mfh_checkbox
  8. _select_radio("ETW")
  9. _click_create_stat + _wait_for_stat_loaded
  10. Body-Text + outerHTML dumpen

Run: .venv/Scripts/python.exe inspectors/diagnose_9_tabellen.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from portals.immometrica.portal import (
    URL_HOME,
    URL_STATISTICS,
    USER_DATA_DIR,
    RUNS_DIR,
    _click_bauliches_tab,
    _click_create_stat,
    _click_marktstatistik_sidebar,
    _do_login,
    _enter_geo,
    _load_env_creds,
    _save_screenshot,
    _select_period,
    _select_radio,
    _set_baujahr_range,
    _ts_slug,
    _uncheck_mfh_checkbox,
    _wait_for_marktstatistik_ready,
    _wait_for_stat_loaded,
)


async def main_async() -> int:
    import nodriver as uc

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts_slug()

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
        # 1. Dashboard
        print(">>> tab.get(URL_HOME)", file=sys.stderr, flush=True)
        tab = await browser.get(URL_HOME)
        await asyncio.sleep(8.0)

        # 2. Login-Check
        body0 = await tab.evaluate(
            "(document.body && document.body.innerText) || ''"
        )
        if isinstance(body0, dict) and "value" in body0:
            body0 = body0["value"]
        body0 = body0 or ""
        if "Logout" not in body0 and "Profil" not in body0:
            print(">>> Session weg - Auto-Login", file=sys.stderr, flush=True)
            user, pw = _load_env_creds()
            if not user or not pw:
                print(">>> .env Credentials fehlen", file=sys.stderr, flush=True)
                return 2
            ok = await _do_login(tab, user, pw)
            if not ok:
                print(">>> Auto-Login fail", file=sys.stderr, flush=True)
                return 3
            await tab.get(URL_HOME)
            await asyncio.sleep(8.0)

        # 3. Sidebar-Klick + Wait auf Form-Hydration
        print(">>> Sidebar-Klick auf Marktstatistik", file=sys.stderr, flush=True)
        clicked = await _click_marktstatistik_sidebar(tab)
        if not clicked:
            print(">>> Sidebar-Klick fail, Fallback URL_STATISTICS",
                  file=sys.stderr, flush=True)
            await tab.get(URL_STATISTICS)
        await asyncio.sleep(5.0)
        ready = await _wait_for_marktstatistik_ready(tab, timeout_s=20.0)
        print(f">>> Marktstatistik-Form bereit: {ready}", file=sys.stderr, flush=True)
        await _save_screenshot(tab, "diag_01_marktstatistik", ts)

        # 4. Geo
        print(">>> Geo 45357 setzen", file=sys.stderr, flush=True)
        geo_ok = await _enter_geo(tab, "45357", "45357")
        print(f">>> Geo OK: {geo_ok}", file=sys.stderr, flush=True)
        await _save_screenshot(tab, "diag_02_geo", ts)

        # 5. Period
        print(">>> Period latest", file=sys.stderr, flush=True)
        await _select_period(tab, "latest")
        await asyncio.sleep(2.0)

        # 6. Bauliches + Baujahr
        print(">>> Bauliches-Tab + Baujahr 1900-1980", file=sys.stderr, flush=True)
        await _click_bauliches_tab(tab)
        await asyncio.sleep(2.0)
        bj_ok = await _set_baujahr_range(tab, 1900, 1980)
        print(f">>> Baujahr OK: {bj_ok}", file=sys.stderr, flush=True)
        await asyncio.sleep(1.0)
        await _save_screenshot(tab, "diag_03_baujahr", ts)

        # 7. MFH aus
        await _uncheck_mfh_checkbox(tab)
        await asyncio.sleep(1.0)

        # 8. Radio ETW
        print(">>> Radio ETW", file=sys.stderr, flush=True)
        await _select_radio(tab, "ETW")
        await asyncio.sleep(2.0)

        # 9. Submit + extended wait
        print(">>> Statistik erstellen", file=sys.stderr, flush=True)
        await _click_create_stat(tab)
        # Server-Response variabel - 90s Timeout sicher
        loaded = await _wait_for_stat_loaded(tab, timeout_s=90.0)
        await asyncio.sleep(3.0)
        print(f">>> Loaded: {loaded}", file=sys.stderr, flush=True)
        await _save_screenshot(tab, "diag_04_result", ts)

        # 10. DOM dumpen
        body_text = await tab.evaluate(
            "(document.body && document.body.innerText) || ''"
        )
        if isinstance(body_text, dict) and "value" in body_text:
            body_text = body_text["value"]
        body_text = body_text or ""

        outer_html = await tab.evaluate(
            "document.documentElement && document.documentElement.outerHTML || ''"
        )
        if isinstance(outer_html, dict) and "value" in outer_html:
            outer_html = outer_html["value"]
        outer_html = outer_html or ""

        # 11. Chart.js-Instanzen dumpen (die 9 Verteilungs-Charts)
        chart_raw = await tab.evaluate(
            """(() => {
                // Chart.js v3+: Chart.instances ist Object oder Map
                let instances = [];
                try {
                    if (window.Chart && Chart.instances) {
                        if (Array.isArray(Chart.instances)) {
                            instances = Chart.instances;
                        } else if (typeof Chart.instances.forEach === 'function') {
                            Chart.instances.forEach(c => instances.push(c));
                        } else {
                            instances = Object.values(Chart.instances);
                        }
                    }
                    // Chart.js v4: Chart.getChart(canvas) waere alternativ
                    if (instances.length === 0 && window.Chart && typeof Chart.getChart === 'function') {
                        document.querySelectorAll('canvas').forEach(c => {
                            const inst = Chart.getChart(c);
                            if (inst) instances.push(inst);
                        });
                    }
                } catch (e) {
                    return JSON.stringify({err: 'access_fail', msg: e.message});
                }
                return JSON.stringify(instances.map(c => {
                    let title = '';
                    try {
                        const canvas = c.canvas || (c.chart && c.chart.canvas);
                        if (canvas) {
                            // Suche Heading-Element in der naehe
                            const wrap = canvas.closest('.col, .col-md, .panel, .card, '
                                + '.form-group, div');
                            if (wrap) {
                                const h = wrap.querySelector('h2, h3, h4, h5, h6, '
                                    + '.chart-title, .title, .heading, b, strong');
                                if (h) title = h.innerText.trim();
                                if (!title) {
                                    // Look for preceding text node
                                    const prev = canvas.previousElementSibling;
                                    if (prev) title = prev.innerText.trim();
                                }
                            }
                        }
                    } catch (e) {}
                    return {
                        canvas_id: (c.canvas && c.canvas.id) || null,
                        title: title,
                        type: c.config ? c.config.type : (c.type || null),
                        labels: (c.data && c.data.labels) || [],
                        datasets: ((c.data && c.data.datasets) || []).map(d => ({
                            label: d.label || null,
                            data: d.data || []
                        }))
                    };
                }));
            })()"""
        )
        if isinstance(chart_raw, dict) and "value" in chart_raw:
            chart_raw = chart_raw["value"]
        chart_path = RUNS_DIR / f"{ts}_diagnose_charts.json"
        if isinstance(chart_raw, str):
            chart_path.write_text(chart_raw, encoding="utf-8")
            print(f">>> Charts: {chart_path} ({len(chart_raw)} chars)",
                  file=sys.stderr, flush=True)

        txt_path = RUNS_DIR / f"{ts}_diagnose_full_dom.txt"
        html_path = RUNS_DIR / f"{ts}_diagnose_full_dom.html"
        txt_path.write_text(body_text, encoding="utf-8")
        html_path.write_text(outer_html, encoding="utf-8")
        print(f">>> Body-Text: {txt_path} ({len(body_text)} chars)",
              file=sys.stderr, flush=True)
        print(f">>> Outer-HTML: {html_path} ({len(outer_html)} chars)",
              file=sys.stderr, flush=True)
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
