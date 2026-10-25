"""Select-Helpers — by index oder by label."""
from __future__ import annotations

from typing import Any


def select_by_index(
    page: Any,
    selector: str,
    index: int,
    option_label: str,
    *,
    settle_ms: int = 150,
) -> None:
    """Wählt in einem <select> per Index in einem Sammel-Selektor."""
    target = page.locator(selector).nth(index)
    target.wait_for(state="attached", timeout=5_000)
    target.select_option(label=option_label)
    page.wait_for_timeout(settle_ms)


def select_by_label(
    page: Any,
    selector: str,
    option_label: str,
    *,
    settle_ms: int = 150,
) -> None:
    """Wählt in einem <select> über einen direkten Selektor (kein nth)."""
    target = page.locator(selector).first
    target.wait_for(state="attached", timeout=5_000)
    target.select_option(label=option_label)
    page.wait_for_timeout(settle_ms)
