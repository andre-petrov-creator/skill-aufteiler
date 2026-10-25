"""Diagnose-Skript: Wo steckt der Cookie-Banner-Button?

Lädt eine URL, wartet lange, dann analysiert ALLE Frames (main + iframes)
nach Buttons/Elementen mit 'akzeptieren'/'zustimmen'-Text. Findet Shadow-DOM-
und iframe-Banner zuverlässig.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")  # type: ignore[assignment]

URL = "https://www.homeday.de/de/preisatlas"

JS_FIND_COOKIE_BUTTONS = """() => {
    // Tiefen-Suche durch DOM + Shadow-DOM nach klickbaren Elementen
    // mit Cookie-Consent-Text
    const KEYWORDS = ['akzeptieren', 'zustimmen', 'einverstanden', 'verstanden',
                      'geht klar', 'einwilligen', 'alle erlauben', 'speichern und'];
    const results = [];

    function walk(root, path) {
        const all = root.querySelectorAll('*');
        for (const el of all) {
            const text = (el.innerText || el.textContent || '').trim().toLowerCase();
            if (text.length === 0 || text.length > 150) continue;
            const tag = el.tagName.toLowerCase();
            const role = el.getAttribute('role');
            const isClickable = tag === 'button' || tag === 'a' || role === 'button'
                                || el.onclick || tag === 'input';
            if (!isClickable) continue;
            for (const kw of KEYWORDS) {
                if (text.includes(kw)) {
                    const rect = el.getBoundingClientRect();
                    results.push({
                        path: path,
                        tag: tag,
                        role: role,
                        id: el.id || null,
                        classes: (el.className || '').toString().slice(0, 200),
                        dataAttrs: Array.from(el.attributes)
                            .filter(a => a.name.startsWith('data-'))
                            .map(a => `${a.name}="${a.value}"`).join(' '),
                        text: text.slice(0, 80),
                        visible: rect.width > 0 && rect.height > 0,
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                    });
                    break;
                }
            }
            // Shadow-DOM rekursiv
            if (el.shadowRoot) {
                walk(el.shadowRoot, path + ' >> shadow(' + tag + ')');
            }
        }
    }
    walk(document, 'main');
    return results;
}"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="de-DE", timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.new_page()
        print(f"Loading {URL}...", file=sys.stderr)
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(8_000)  # Cookie-Banner kann verzögert kommen

        print(f"\nGesamt-Frames: {len(page.frames)}", file=sys.stderr)
        for i, frame in enumerate(page.frames):
            print(f"  Frame {i}: url={frame.url[:80]}", file=sys.stderr)

        all_results: list[dict] = []
        for i, frame in enumerate(page.frames):
            try:
                buttons = frame.evaluate(JS_FIND_COOKIE_BUTTONS)
                for b in buttons:
                    b["frame_idx"] = i
                    b["frame_url"] = frame.url[:80]
                all_results.extend(buttons)
            except Exception as e:
                print(f"  Frame {i} evaluate failed: {e}", file=sys.stderr)

        # JSON-Dump
        Path("runs/homeday_cookie_diagnose.json").write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"\nGefundene Cookie-Consent-Kandidaten: {len(all_results)}", file=sys.stderr)
        for r in all_results:
            print(
                f"  [{r.get('frame_idx')}] <{r['tag']}> "
                f"role={r['role']!r} id={r['id']!r} "
                f"vis={r['visible']} "
                f"text={r['text']!r} "
                f"classes={r['classes'][:60]!r} "
                f"path={r['path']}",
                file=sys.stderr,
            )

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
