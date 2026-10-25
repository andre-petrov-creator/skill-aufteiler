"""Inspector: füllt das Formular minimal, klickt Kaufen, dann dumpt
alle Radio-Inputs (insb. die Zeitrahmen-Radios)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://baufinanzierung.check24.de/baufinanzierung/immobilienbewertung?deviceoutput=desktop"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 1600})
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    for c in ['button:has-text("geht klar")', '#check24-cookie-acceptAll']:
        try:
            page.locator(c).first.click(timeout=2000)
            break
        except Exception:
            pass
    page.wait_for_timeout(1500)

    # Klicke Kaufen, damit der Zeitrahmen-Block erscheint
    try:
        page.locator('xpath=//input[@qa-ref="property-evaluation-purpose-0"]/ancestor::label[1]').first.click(timeout=5000)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Kaufen-Klick fehlgeschlagen: {e}")

    radios = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('input[type="radio"]').forEach((el, i) => {
            const label = el.closest('label');
            out.push({
                idx: i,
                qaRef: el.getAttribute('qa-ref'),
                name: el.name,
                value: el.value,
                cls: (el.className||'').toString().slice(0,80),
                label_text: (label ? label.innerText : '').trim().slice(0,80),
                label_cls: (label ? (label.className||'').toString().slice(0,80) : ''),
            });
        });
        return out;
    }""")
    Path("timing_radios.json").write_text(json.dumps(radios, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Found {len(radios)} radios:")
    for r in radios:
        print(f"  [{r['idx']}] qa-ref={r['qaRef']!r:40s} name={r['name']!r} val={r['value']!r} label={r['label_text']!r}")

    browser.close()
