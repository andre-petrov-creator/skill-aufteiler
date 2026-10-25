"""Input-Helpers — Tippen mit press_sequentially + Autocomplete-Pattern."""
from __future__ import annotations

import re
from typing import Any

from core.log import log


def input_typed(
    page: Any,
    selector: str,
    value: str,
    *,
    index: int = 0,
    type_delay_ms: int = 80,
    settle_ms: int = 300,
) -> None:
    """Tippt einen Wert in ein Input — leert vorher, dispatcht change-Event + Tab.

    `selector` kann ein Sammel-Selektor sein, dann wird `nth(index)` benutzt.
    """
    target = page.locator(selector).nth(index) if index else page.locator(selector).first
    # force=True umgeht overlay-intercepts (z.B. CHECK24-Cookie-Banner).
    # Analog zu core/radios.py — Inputs hatten das Pattern bisher nicht,
    # wodurch CHECK24 mit sichtbarem Cookie-Banner scheiterte.
    target.click(force=True)
    target.evaluate("el => el.value = ''")
    target.press_sequentially(value, delay=type_delay_ms)
    target.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
    target.press("Tab")
    page.wait_for_timeout(settle_ms)


def normalize_strasse_abbrev(value: str) -> str:
    """Portale mit Geo-Autocomplete erwarten 'Str.' statt 'Straße'/'Strasse'."""
    normalized = re.sub(r"straße\b", "str.", value, flags=re.IGNORECASE)
    normalized = re.sub(r"strasse\b", "str.", normalized, flags=re.IGNORECASE)
    return normalized


def input_street_with_autocomplete(
    page: Any,
    selector: str,
    value: str,
    *,
    index: int = 0,
    normalize_abbrev: bool = True,
    type_delay_ms: int = 120,
    wait_for_suggestions_ms: int = 1_800,
    settle_ms: int = 600,
) -> str:
    """Tippt eine Straße + drückt Enter — für Portale mit Geo-Autocomplete.

    Returns: den tatsächlich getippten String (nach Normalisierung).
    """
    short = normalize_strasse_abbrev(value) if normalize_abbrev else value
    target = page.locator(selector).nth(index) if index else page.locator(selector).first
    target.click(force=True)
    target.evaluate("el => el.value = ''")
    target.press_sequentially(short, delay=type_delay_ms)
    page.wait_for_timeout(wait_for_suggestions_ms)
    target.press("Enter")
    page.wait_for_timeout(settle_ms)
    log(f"Straße eingegeben: {short!r}")
    return short
