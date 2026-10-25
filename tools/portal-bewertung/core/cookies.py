"""Cookie-Banner-Dismisser — pollt bis Banner verschwindet.

Generisch genug für CHECK24, Homeday, Interhyp, IS24 — der Portal-Adapter
liefert eigene `accept_candidates` und `wrapper_selector`.
"""
from __future__ import annotations

import time
from typing import Any, Optional


def _wrapper_present(page: Any, wrapper_selector: str) -> bool:
    try:
        wrapper = page.locator(wrapper_selector).first
        return wrapper.count() > 0 and wrapper.is_visible()
    except Exception:
        return False


def _click_first_visible(page: Any, accept_candidates: list[str]) -> bool:
    for selector in accept_candidates:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3_000)
                return True
        except Exception:
            continue
    return False


def dismiss_cookies(
    page: Any,
    accept_candidates: list[str],
    wrapper_selector: Optional[str] = None,
    max_wait_s: float = 15.0,
    fallback_remove_selectors: Optional[list[str]] = None,
) -> bool:
    """Wartet bis Cookie-Banner verschwindet oder geklickt wurde.

    Wenn `wrapper_selector` angegeben: wartet bis Wrapper nicht mehr sichtbar
    (auch nach Click pollen). Sonst nur ein Klick-Versuch.

    `fallback_remove_selectors`: Wenn nichts klappt, werden diese Elemente per
    JS entfernt (letzte Notbremse, sollte selten greifen).
    """
    deadline = time.monotonic() + max_wait_s
    clicked_once = False
    while time.monotonic() < deadline:
        if wrapper_selector and not _wrapper_present(page, wrapper_selector):
            return clicked_once
        if _click_first_visible(page, accept_candidates):
            clicked_once = True
            page.wait_for_timeout(500)
            if wrapper_selector and not _wrapper_present(page, wrapper_selector):
                return True
        if not wrapper_selector and clicked_once:
            return True
        page.wait_for_timeout(400)

    if fallback_remove_selectors:
        try:
            js_selectors = ", ".join(repr(s) for s in fallback_remove_selectors)
            page.evaluate(
                f"document.querySelectorAll([{js_selectors}].join(',')).forEach(el => el.remove());"
            )
        except Exception:
            pass
    return clicked_once
