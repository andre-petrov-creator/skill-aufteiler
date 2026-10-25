"""Unit-Tests für core/modals.py — generischer Modal-Dismisser.

Wir mocken Playwright-Page per Dummy-Klasse: kein echter Browser nötig.
"""
from __future__ import annotations

from typing import Optional

from core.modals import dismiss_modal_by_text


class FakeLocator:
    def __init__(self, count: int = 0, visible: bool = False) -> None:
        self._count = count
        self._visible = visible
        self.click_called = False
        self.click_timeout: Optional[int] = None

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return self._count

    def is_visible(self) -> bool:
        return self._visible

    def click(self, timeout: int = 0) -> None:
        self.click_called = True
        self.click_timeout = timeout


class FakePage:
    def __init__(self, locator_map: dict[str, FakeLocator]) -> None:
        self._map = locator_map
        self.wait_calls: list[int] = []

    def locator(self, selector: str) -> FakeLocator:
        return self._map.get(selector, FakeLocator(count=0, visible=False))

    def wait_for_timeout(self, ms: int) -> None:
        self.wait_calls.append(ms)


def test_dismiss_modal_by_text_clicks_first_visible_match() -> None:
    target = FakeLocator(count=1, visible=True)
    page = FakePage(
        {
            'button:has-text("OK")': FakeLocator(count=0, visible=False),
            'button:has-text("später erinnern")': target,
        }
    )
    clicked = dismiss_modal_by_text(
        page, accept_texts=["OK", "später erinnern", "Schließen"]
    )
    assert clicked is True
    assert target.click_called is True


def test_dismiss_modal_by_text_returns_false_when_nothing_visible() -> None:
    page = FakePage(
        {
            'button:has-text("OK")': FakeLocator(count=1, visible=False),
            'button:has-text("Cancel")': FakeLocator(count=0, visible=False),
        }
    )
    clicked = dismiss_modal_by_text(page, accept_texts=["OK", "Cancel"])
    assert clicked is False


def test_dismiss_modal_by_text_skips_invisible_then_clicks_visible() -> None:
    invisible = FakeLocator(count=1, visible=False)
    visible = FakeLocator(count=1, visible=True)
    page = FakePage(
        {
            'button:has-text("Erste")': invisible,
            'button:has-text("Zweite")': visible,
        }
    )
    clicked = dismiss_modal_by_text(page, accept_texts=["Erste", "Zweite"])
    assert clicked is True
    assert invisible.click_called is False
    assert visible.click_called is True


def test_dismiss_modal_by_text_empty_list_returns_false() -> None:
    page = FakePage({})
    clicked = dismiss_modal_by_text(page, accept_texts=[])
    assert clicked is False
