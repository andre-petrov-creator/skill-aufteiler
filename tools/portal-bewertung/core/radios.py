"""Radio-Klicker — mit optionalem Pfeil-Nudge für React-States."""
from __future__ import annotations

import re
from typing import Any

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
except ImportError:  # pragma: no cover — Playwright optional bei reinen Helper-Tests
    PlaywrightTimeoutError = Exception  # type: ignore[assignment,misc]


def click_radio(
    page: Any,
    qa_ref_selector: str,
    *,
    nudge_keys: bool = True,
    settle_ms: int = 300,
) -> bool:
    """Klickt ein Radio per `qa-ref`-Attribut.

    Mit `nudge_keys=True`: nach dem Klick werden 2× ArrowLeft, 2× ArrowRight,
    dann Enter gedrückt — manche React-Forms registrieren den Klick nur als
    'changed', wenn auch eine Tastatur-Interaktion folgt.

    Erwartet einen Selektor wie `'input[qa-ref="kaufabsicht-kauf"]'`.
    """
    ref_match = re.search(r'qa-ref="([^"]+)"', qa_ref_selector)
    if not ref_match:
        return False
    ref = ref_match.group(1)

    label_locator = page.locator(f'xpath=//input[@qa-ref="{ref}"]/ancestor::label[1]')

    clicked = False
    try:
        label_locator.scroll_into_view_if_needed(timeout=3_000)
        page.wait_for_timeout(200)
        label_locator.click(timeout=5_000)
        clicked = True
    except PlaywrightTimeoutError:
        try:
            page.locator(qa_ref_selector).first.click(force=True, timeout=3_000)
            clicked = True
        except PlaywrightTimeoutError:
            pass

    if clicked and nudge_keys:
        page.wait_for_timeout(200)
        try:
            input_loc = page.locator(qa_ref_selector).first
            input_loc.evaluate("el => el.focus()")
            page.wait_for_timeout(150)
            for _ in range(2):
                page.keyboard.press("ArrowLeft")
                page.wait_for_timeout(120)
            for _ in range(2):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(120)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
        except Exception:
            pass
    page.wait_for_timeout(settle_ms)
    return clicked


def click_radio_by_label_text(
    page: Any,
    label_text: str,
    *,
    nudge_keys: bool = True,
    settle_ms: int = 400,
) -> bool:
    """Klickt ein Radio per sichtbarem Label-Text (z.B. '1-3 Monate').

    Mit `nudge_keys=True`: 2× ArrowRight, 2× ArrowLeft als Tastatur-Nudge.
    """
    try:
        label_loc = page.locator(f'label:has-text("{label_text}")').first
        label_loc.scroll_into_view_if_needed(timeout=3_000)
        page.wait_for_timeout(200)
        label_loc.click(timeout=5_000)
        page.wait_for_timeout(settle_ms)
    except PlaywrightTimeoutError:
        try:
            page.get_by_text(label_text, exact=False).first.click(timeout=3_000)
            page.wait_for_timeout(settle_ms)
        except Exception:
            return False

    if nudge_keys:
        for _ in range(2):
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(120)
        for _ in range(2):
            page.keyboard.press("ArrowLeft")
            page.wait_for_timeout(120)
        page.wait_for_timeout(settle_ms)
    return True
