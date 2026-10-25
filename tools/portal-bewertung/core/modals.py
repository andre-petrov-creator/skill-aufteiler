"""Generischer Modal-Dismisser — Page-Objekt-basiert, portal-agnostisch.

Wird von Portal-Adaptern und Runner aufgerufen, um Cookie-Banner und
Post-Submit-Overlays per Text-Match zu schließen.
"""
from __future__ import annotations

from typing import Protocol


class _Locator(Protocol):
    @property
    def first(self) -> "_Locator": ...
    def count(self) -> int: ...
    def is_visible(self) -> bool: ...
    def click(self, timeout: int = 0) -> None: ...


class _Page(Protocol):
    def locator(self, selector: str) -> _Locator: ...
    def wait_for_timeout(self, ms: int) -> None: ...


def dismiss_modal_by_text(
    page: _Page,
    accept_texts: list[str],
    *,
    click_timeout_ms: int = 3_000,
    settle_ms: int = 400,
) -> bool:
    """Sucht nacheinander Buttons mit den gegebenen Texten und klickt den ersten
    sichtbaren. Returns True wenn geklickt, sonst False.

    Es wird das gleiche `:has-text("...")`-Pattern für jeden Text probiert —
    Playwright matched substring, daher reicht ein kurzer Text-Anker
    (z.B. ["OK", "später erinnern"]).
    """
    for text in accept_texts:
        selector = f'button:has-text("{text}")'
        try:
            loc = page.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=click_timeout_ms)
                page.wait_for_timeout(settle_ms)
                return True
        except Exception:
            continue
    return False
