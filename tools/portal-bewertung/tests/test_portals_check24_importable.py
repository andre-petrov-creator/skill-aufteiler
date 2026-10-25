"""Smoke-Test für portals/check24/. Live-Verifikation via CLI in Step 8."""
from __future__ import annotations


def test_check24_portal_imports_and_subclasses_portal_base() -> None:
    from core.portal_base import PortalBase
    from portals.check24.portal import Check24Portal

    assert issubclass(Check24Portal, PortalBase)
    portal = Check24Portal()
    assert portal.NAME == "check24"
    assert portal.START_URL.startswith("https://")
    assert portal.SUBMIT_SELECTOR
    assert portal.RESULT_FRAME_MARKER == "Marktwertermittlung"
    assert len(portal.COOKIE_ACCEPT_CANDIDATES) > 0


def test_check24_selectors_module_has_required_constants() -> None:
    from portals.check24 import selectors as sel

    assert sel.START_URL
    assert sel.SUBMIT_BUTTON
    assert sel.FORM_INPUTS
    assert sel.FORM_SELECTS
    assert "gut" in sel.ZUSTAND_OPTION
    assert "normal" in sel.AUSSTATTUNG_OPTION
    assert "wohnung" in sel.IMMOTYP_OPTION
