"""Unit-Tests für core/llm_recovery.py mit mocked Anthropic-Client."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from core.llm_recovery import recover_selector


class FakePage:
    def __init__(
        self,
        *,
        html_dump: str = "<html><body></body></html>",
        candidate_works: bool = True,
    ) -> None:
        self.html_dump = html_dump
        self.candidate_works = candidate_works
        self.screenshot_calls: list[str] = []

    def evaluate(self, _script: str, *args: Any) -> str:
        return self.html_dump

    def locator(self, _selector: str) -> Any:
        loc = MagicMock()
        loc.first.count.return_value = 1 if self.candidate_works else 0
        loc.first.is_visible.return_value = True
        return loc

    def screenshot(self, *, path: str = "", **kwargs: Any) -> bytes:
        self.screenshot_calls.append(path)
        return b"\x89PNG\r\n\x1a\n"


def _make_anthropic_client(returned_selector: str = '#new-selector') -> MagicMock:
    """Liefert einen Mock-Client, der ein Selektor-Snippet zurückgibt."""
    client = MagicMock()
    # Antwort-Struktur matched anthropic-SDK 0.x messages.create response
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = f'```css\n{returned_selector}\n```'
    msg = MagicMock()
    msg.content = [text_block]
    client.messages.create.return_value = msg
    return client


def test_recover_selector_returns_validated_selector_from_client() -> None:
    client = _make_anthropic_client(returned_selector='button[data-test="ok"]')
    page = FakePage(candidate_works=True)

    out = recover_selector(
        page,
        failed_selector='button:has-text("OK")',
        intent="cookie_accept",
        portal_name="check24",
        client=client,
    )

    assert out == 'button[data-test="ok"]'
    client.messages.create.assert_called_once()


def test_recover_selector_returns_none_when_candidate_does_not_match() -> None:
    client = _make_anthropic_client(returned_selector="#never-matches")
    page = FakePage(candidate_works=False)

    out = recover_selector(
        page,
        failed_selector="#old",
        intent="submit",
        portal_name="check24",
        client=client,
    )
    assert out is None


def test_recover_selector_returns_none_when_no_client_available() -> None:
    page = FakePage()
    out = recover_selector(
        page,
        failed_selector="#old",
        intent="x",
        portal_name="check24",
        client=None,
    )
    assert out is None


def test_recover_selector_strips_code_fence_and_quotes() -> None:
    # Manchmal liefert das LLM extra Anführungszeichen oder ```html-Fences
    client = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = '```\n"button.primary"\n```'
    msg = MagicMock()
    msg.content = [text_block]
    client.messages.create.return_value = msg

    page = FakePage(candidate_works=True)
    out = recover_selector(
        page,
        failed_selector="#old",
        intent="submit",
        portal_name="check24",
        client=client,
    )
    assert out == "button.primary"
