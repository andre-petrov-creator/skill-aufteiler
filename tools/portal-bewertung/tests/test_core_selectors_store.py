"""Unit-Tests für core/selectors_store.py — Persistenz gelernter Selektoren."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.selectors_store import load_learned_selectors, save_learned_selector


def test_load_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    out = load_learned_selectors("nope", base_dir=tmp_path)
    assert out == {}


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    save_learned_selector(
        "check24",
        intent="cookie_accept",
        selector='button:has-text("OK")',
        base_dir=tmp_path,
    )
    out = load_learned_selectors("check24", base_dir=tmp_path)
    assert out == {"cookie_accept": 'button:has-text("OK")'}


def test_save_multiple_intents_into_same_file(tmp_path: Path) -> None:
    save_learned_selector("homeday", "plz", "#zip", base_dir=tmp_path)
    save_learned_selector("homeday", "strasse", "#street", base_dir=tmp_path)
    out = load_learned_selectors("homeday", base_dir=tmp_path)
    assert out == {"plz": "#zip", "strasse": "#street"}


def test_save_overwrites_existing_intent(tmp_path: Path) -> None:
    save_learned_selector("x", "submit", "#old", base_dir=tmp_path)
    save_learned_selector("x", "submit", "#new", base_dir=tmp_path)
    out = load_learned_selectors("x", base_dir=tmp_path)
    assert out == {"submit": "#new"}


def test_save_rejects_empty_portal_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_learned_selector("", "intent", "#sel", base_dir=tmp_path)


def test_save_rejects_empty_selector(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_learned_selector("x", "intent", "", base_dir=tmp_path)
