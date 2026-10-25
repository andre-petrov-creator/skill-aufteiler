"""Debug-Skript: Statistik-Page DOM-Struktur inspizieren.

Speziell: Wie sind Ort-Tags + Eingabefeld + Trash-Buttons im HTML aufgebaut?
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
        await asyncio.sleep(4.0)

        # Komplettes HTML der Ort-Box dumpen
        ort_html = await tab.evaluate(
            """(() => {
                // Suche die <label> oder <h6> mit Text "Ort"
                const all = Array.from(document.querySelectorAll('*'));
                const ortHeaders = all.filter(el => {
                    const t = el.innerText || '';
                    return /^(\\s*Ort\\s*)$/.test(t) || t.trim() === 'Ort';
                }).filter(el => el.tagName !== 'OPTION');
                if (ortHeaders.length === 0) return 'KEIN Ort-Header gefunden';
                // Naehester Container
                const header = ortHeaders[0];
                const container = header.closest('div.card, div.panel, .container, fieldset')
                    || header.parentElement.parentElement;
                return container ? container.outerHTML.substring(0, 8000) : 'kein Container';
            })()"""
        )
        if isinstance(ort_html, dict) and "value" in ort_html:
            ort_html = ort_html["value"]
        p = RUNS_DIR / "debug_immometrica_ort_html.txt"
        p.write_text(str(ort_html), encoding="utf-8")
        print(f">>> Ort-HTML gedumpt: {p.name}")

        # Alle Buttons in der Ort-Box mit aria-label
        btns = await tab.evaluate(
            """(() => {
                const all = Array.from(document.querySelectorAll('button, a, i, [role="button"]'));
                return JSON.stringify(all
                    .filter(b => {
                        const r = b.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    })
                    .map(b => ({
                        tag: b.tagName,
                        cls: b.className,
                        id: b.id,
                        text: (b.innerText || '').trim().slice(0, 50),
                        aria: b.getAttribute('aria-label'),
                        onclick: !!b.onclick,
                        href: b.getAttribute('href'),
                    }))
                    .filter(b => b.cls && (
                        b.cls.includes('trash') || b.cls.includes('delete')
                        || b.cls.includes('remove') || b.cls.includes('close')
                        || b.cls.includes('select2')
                    ))
                );
            })()"""
        )
        if isinstance(btns, dict) and "value" in btns:
            btns = btns["value"]
        p = RUNS_DIR / "debug_immometrica_buttons.json"
        p.write_text(str(btns), encoding="utf-8")
        print(f">>> Buttons gedumpt: {p.name}")
        print(f">>> Buttons-snippet: {str(btns)[:500]}")

        # Alle Inputs in der Ort-Box
        inputs = await tab.evaluate(
            """(() => {
                return JSON.stringify(Array.from(document.querySelectorAll('input'))
                    .map(i => ({
                        type: i.type,
                        name: i.name,
                        id: i.id,
                        cls: i.className.slice(0, 100),
                        placeholder: i.placeholder,
                        visible: i.offsetParent !== null,
                    }))
                    .filter(i => i.visible || i.placeholder));
            })()"""
        )
        if isinstance(inputs, dict) and "value" in inputs:
            inputs = inputs["value"]
        p = RUNS_DIR / "debug_immometrica_inputs.json"
        p.write_text(str(inputs), encoding="utf-8")
        print(f">>> Inputs gedumpt: {p.name}")
        print(f">>> Inputs-snippet: {str(inputs)[:1500]}")

        # Screenshot
        await tab.save_screenshot(filename=str(RUNS_DIR / "debug_immometrica_stat_page.png"))
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
