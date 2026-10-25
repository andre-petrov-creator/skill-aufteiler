"""Smoke-Test für portals/homeday/. Live-Verifikation via CLI."""
from __future__ import annotations


def test_homeday_portal_imports_and_subclasses_portal_base() -> None:
    from core.portal_base import PortalBase
    from portals.homeday.portal import HomedayPortal

    assert issubclass(HomedayPortal, PortalBase)
    portal = HomedayPortal()
    assert portal.NAME == "homeday"
    assert portal.START_URL.startswith("https://")
    assert portal.SUBMIT_SELECTOR == ""  # Deep-Link, kein Submit
    assert portal.RESULT_FRAME_MARKER == "Aktueller Kaufpreis"
    assert "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll" in portal.COOKIE_ACCEPT_CANDIDATES


def test_homeday_portal_constructor_takes_marketing_and_property_type() -> None:
    from portals.homeday.portal import HomedayPortal

    p1 = HomedayPortal()
    assert p1.marketing_type == "sell"
    assert p1.property_type == "apartment"

    p2 = HomedayPortal(marketing_type="rent", property_type="house")
    assert p2.marketing_type == "rent"
    assert p2.property_type == "house"


def test_homeday_in_cli_registry() -> None:
    import m00_portal_pricer

    assert "homeday" in m00_portal_pricer.PORTAL_REGISTRY


def test_homeday_extract_extra_from_real_body_text() -> None:
    """Mit echtem Body-Text-Sample von Prosperstraße 59 (Mai 2026)."""
    from portals.homeday.portal import parse_homeday_extras

    body = (
        "Aktueller Kaufpreis\n"
        "Ø 1.700 €/m²\n"
        "PREISTREND ÜBER 12 MONATE\n"
        "Stadt\n+6 %\n"
        "Wohnblock\n—\n"
        "Wohnlage\nEinfach\n"
    )
    out = parse_homeday_extras(body)
    assert out["eur_per_qm"] == 1700
    assert out["trend_12m_stadt_pct"] == 6.0
    assert out["trend_12m_stadt_ampel"] == "gruen"
    assert out["trend_12m_wohnblock_pct"] is None
    assert out["trend_12m_wohnblock_ampel"] == "grau"
    assert out["wohnblock_wohnlage"] == "einfach"
    assert out["wohnblock_farbe_hex"] == "#FFE873"
