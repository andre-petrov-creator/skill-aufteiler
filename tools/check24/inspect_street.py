"""Inspector: tippt Prosperstraße und dumpt, was im DOM erscheint."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://baufinanzierung.check24.de/baufinanzierung/immobilienbewertung?deviceoutput=desktop"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(locale="de-DE", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)

    for sel_cookie in ['button:has-text("geht klar")', 'button:has-text("Geht klar")', '#check24-cookie-acceptAll']:
        try:
            page.locator(sel_cookie).first.click(timeout=2000)
            page.wait_for_timeout(800)
            break
        except Exception:
            pass

    page.wait_for_selector('input.input', timeout=10000)
    page.locator('select.select').nth(0).select_option(label="Eigentumswohnung")
    page.wait_for_timeout(500)

    plz = page.locator('input.input').nth(0)
    plz.click()
    plz.type("45357", delay=80)
    plz.press("Tab")
    page.wait_for_timeout(1500)

    strasse = page.locator('input.input').nth(1)
    strasse.click()
    strasse.type("Prosperstra", delay=100)
    page.wait_for_timeout(3000)

    dom = page.evaluate("""() => {
        const found = [];
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length > 0 && el.children.length < 50) return;
            const txt = (el.textContent || '').trim();
            if (!txt || txt.length > 300) return;
            if (/Prosper/i.test(txt)) {
                found.push({
                    tag: el.tagName,
                    cls: (el.className || '').toString().slice(0,120),
                    role: el.getAttribute('role') || '',
                    text: txt.slice(0,150),
                    visible: el.offsetParent !== null,
                    parent_tag: el.parentElement ? el.parentElement.tagName : '',
                    parent_cls: el.parentElement ? (el.parentElement.className || '').toString().slice(0,120) : '',
                });
            }
        });
        return found.slice(0, 30);
    }""")
    Path("street_dom.json").write_text(json.dumps(dom, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Prosper-matching elements: {len(dom)}")
    for d in dom[:10]:
        print(f"  {d['tag']}.{d['cls'][:50]} role={d['role']!r} vis={d['visible']} text={d['text'][:80]!r}")

    page.screenshot(path="runs/inspect_street.png", full_page=True)
    browser.close()
