"""DOM-Inspector — öffnet CHECK24, akzeptiert Cookies, dumpt Form-Elemente
mit ihren zugehörigen <label>-Texten (floating-label-Pattern).

Lauf:
    .venv\\Scripts\\python.exe inspect_form.py
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://baufinanzierung.check24.de/baufinanzierung/immobilienbewertung?deviceoutput=desktop"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(locale="de-DE")
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)

    for sel in ['button:has-text("geht klar")', 'button:has-text("Geht klar")']:
        try:
            page.locator(sel).first.click(timeout=2000)
            break
        except Exception:
            pass
    page.wait_for_timeout(1500)

    inputs = page.eval_on_selector_all(
        'input.input',
        """els => els.map(e => {
            let lbl = '';
            let parent = e.parentElement;
            for (let i = 0; i < 4 && parent; i++) {
                const l = parent.querySelector('label, .styleguide__CustomInput__label, [class*=label]');
                if (l && l.textContent.trim()) { lbl = l.textContent.trim().slice(0,60); break; }
                parent = parent.parentElement;
            }
            return {
                tag: 'INPUT',
                type: e.type,
                placeholder: e.placeholder,
                qaRef: e.getAttribute('qa-ref'),
                maxlength: e.maxLength,
                label: lbl,
            };
        })"""
    )
    selects = page.eval_on_selector_all(
        'select.select',
        """els => els.map(e => {
            let lbl = '';
            let parent = e.parentElement;
            for (let i = 0; i < 4 && parent; i++) {
                const l = parent.querySelector('label, [class*=label]');
                if (l && l.textContent.trim()) { lbl = l.textContent.trim().slice(0,60); break; }
                parent = parent.parentElement;
            }
            return {
                tag: 'SELECT',
                qaRef: e.getAttribute('qa-ref'),
                options: Array.from(e.options).map(o => o.text).slice(0,8),
                label: lbl,
            };
        })"""
    )
    radios = page.eval_on_selector_all(
        'input[type="radio"]',
        """els => els.map(e => {
            let lbl = '';
            let parent = e.parentElement;
            for (let i = 0; i < 4 && parent; i++) {
                const txt = parent.innerText || '';
                if (txt && txt.length < 80) { lbl = txt.trim(); break; }
                parent = parent.parentElement;
            }
            return {
                tag: 'RADIO',
                qaRef: e.getAttribute('qa-ref'),
                value: e.value,
                label: lbl,
            };
        })"""
    )

    dump = {"inputs": inputs, "selects": selects, "radios": radios}
    Path("form_dump.json").write_text(
        json.dumps(dump, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"Inputs: {len(inputs)} | Selects: {len(selects)} | Radios: {len(radios)} -> form_dump.json"
    )
    browser.close()
