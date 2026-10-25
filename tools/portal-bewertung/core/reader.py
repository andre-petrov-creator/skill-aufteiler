"""Frame-Reader — Result-Frame finden + Deep-Scroll + Text-Extract.

Portal-agnostisch: der Portal-Adapter liefert den Marker-Text, der den
relevanten Frame identifiziert (z.B. 'Marktwertermittlung').
"""
from __future__ import annotations

import time
from typing import Any, Optional

from core.log import log


def find_result_frame(
    page: Any,
    marker_text: str,
    *,
    scan_timeout_ms: int = 2_000,
    max_wait_s: float = 15.0,
) -> Optional[Any]:
    """Sucht in allen Page-Frames nach einem Frame, dessen body den Marker enthält.

    Pollt bis zu `max_wait_s` Sekunden — Result-iframes (PriceHubble bei
    CHECK24, andere bei Homeday) laden asynchron nach Submit, und der
    Marker-Text erscheint erst nach Cookie-Consent + Render-Pass.
    """
    deadline = time.monotonic() + max_wait_s
    while True:
        for frame in page.frames:
            try:
                text = frame.locator("body").inner_text(timeout=scan_timeout_ms)
            except Exception:
                continue
            if marker_text in text:
                log(f"Result-Frame mit Marker {marker_text!r} gefunden: {frame.url[:80]}")
                return frame
        if time.monotonic() >= deadline:
            return None
        time.sleep(1.0)


def deep_scroll_frame(frame: Any, *, steps: int = 20, step_delay_ms: int = 250) -> None:
    """Scrollt im Frame alle scrollbaren Container schrittweise nach unten.

    PriceHubble + andere lazy-loaden Inhalte beim Scrollen, daher reicht ein
    einfaches window-scroll nicht.
    """
    try:
        frame.evaluate(
            """(args) => {
                return new Promise(resolve => {
                    const findScrollable = () => {
                        const els = Array.from(document.querySelectorAll('*'));
                        return els.filter(el => {
                            const cs = getComputedStyle(el);
                            return (cs.overflowY === 'auto' || cs.overflowY === 'scroll')
                                && el.scrollHeight > el.clientHeight + 50;
                        });
                    };
                    let step = 0;
                    const iv = setInterval(() => {
                        const scrollables = findScrollable();
                        scrollables.forEach(el => { el.scrollTop = el.scrollTop + 800; });
                        window.scrollBy(0, 800);
                        step++;
                        if (step >= args.steps) { clearInterval(iv); resolve(); }
                    }, args.delay);
                });
            }""",
            {"steps": steps, "delay": step_delay_ms},
        )
    except Exception as e:
        log(f"Deep-Scroll fehlgeschlagen: {e}")


def read_frame_body_deep(frame: Any) -> str:
    """Liest den vollständigen sichtbaren Text aus einem Frame inkl. dynamisch
    gerenderter Children. Filtert display:none + visibility:hidden raus.
    """
    try:
        text = frame.evaluate(
            """() => {
                const allText = [];
                document.querySelectorAll('*').forEach(el => {
                    const cs = getComputedStyle(el);
                    if (cs.display === 'none' || cs.visibility === 'hidden') return;
                    const own = Array.from(el.childNodes)
                        .filter(n => n.nodeType === 3)
                        .map(n => n.textContent.trim()).filter(t => t).join(' ');
                    if (own) allText.push(own);
                });
                return allText.join('\\n');
            }"""
        )
        log(f"Frame-Body extrahiert: {len(text)} Zeichen.")
        return text or ""
    except Exception:
        return ""


def read_page_body_deep(page: Any) -> str:
    """Fallback wenn kein Result-Frame gefunden wurde — liest die ganze Page."""
    try:
        return page.evaluate(
            """() => {
                function collect(root) {
                    let texts = [];
                    root.querySelectorAll('*').forEach(el => {
                        if (el.shadowRoot) texts.push(el.shadowRoot.textContent || '');
                        const cs = getComputedStyle(el);
                        if (cs.display !== 'none' && cs.visibility !== 'hidden') {
                            const own = Array.from(el.childNodes)
                                .filter(n => n.nodeType === 3)
                                .map(n => n.textContent).join(' ');
                            if (own.trim()) texts.push(own);
                        }
                    });
                    return texts.join('\\n');
                }
                return collect(document.body);
            }"""
        )
    except Exception:
        try:
            return page.locator("body").inner_text()
        except Exception:
            return ""
