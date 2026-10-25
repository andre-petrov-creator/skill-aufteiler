"""Smoke-Tests fuer portals/interhyp/."""
from __future__ import annotations

from core.portal_base import PortalBase


def test_interhyp_portal_imports_and_subclasses_portal_base() -> None:
    from portals.interhyp.portal import InterhypPortal

    assert issubclass(InterhypPortal, PortalBase)
    p = InterhypPortal()
    assert p.NAME == "interhyp"
    assert p.START_URL.startswith("https://www.interhyp.de/")
    # SUBMIT_SELECTOR leer — fill_form klickt selbst 'Ergebnisse anzeigen'
    assert p.SUBMIT_SELECTOR == ""
    assert "Ihr Immobilienwert" in p.RESULT_FRAME_MARKER


def test_interhyp_selectors_exposes_required_constants() -> None:
    from portals.interhyp import selectors as sel

    assert sel.START_URL.startswith("https://")
    assert isinstance(sel.COOKIE_ACCEPT_CANDIDATES, list)
    assert sel.SUBMIT_TEXT_WIZARD == "Ergebnisse anzeigen"
    # Mapping muss alle gueltigen Ausstattungs-Werte abdecken
    for value in ("einfach", "normal", "gehoben", "luxus"):
        assert value in sel.STEP8_AUSSTATTUNG_MAP


def test_interhyp_in_portal_registry() -> None:
    from m00_portal_pricer import PORTAL_REGISTRY
    from portals.interhyp.portal import InterhypPortal

    assert "interhyp" in PORTAL_REGISTRY
    assert PORTAL_REGISTRY["interhyp"] is InterhypPortal


def test_interhyp_extract_extra_with_sample_body() -> None:
    """Verifiziert, dass extract_extra alle erwarteten Keys liefert.

    Trend-2J kann None sein (Page-Mock), aber alle Marktwert-Felder muessen
    aus dem Body geparst werden.
    """
    from portals.interhyp.portal import InterhypPortal

    body = (
        "Ihr Immobilienwert betraegt\n183.000 EUR\n"
        "Untergrenze\n157.000 EUR\n"
        "Schaetzwert*\n183.000 EUR\n"
        "Obergrenze\n207.000 EUR\n"
        "Einfach\n183.000 EUR\n2.288 EUR/m²\n"
        "Gehoben\n194.000 EUR\n2.425 EUR/m²\n"
        "Luxus\n215.000 EUR\n2.688 EUR/m²\n"
    )

    class FakeLocator:
        def __init__(self) -> None:
            self.first = self

        def count(self) -> int:
            return 0

        def is_visible(self) -> bool:
            return False

        def click(self, **kwargs: object) -> None:  # pragma: no cover - not reached
            pass

        def inner_text(self, **kwargs: object) -> str:
            return ""

    class FakePage:
        def locator(self, _selector: str) -> FakeLocator:
            return FakeLocator()

        def get_by_label(self, _label: str, exact: bool = False) -> FakeLocator:
            return FakeLocator()

        def get_by_placeholder(self, _label: str) -> FakeLocator:
            return FakeLocator()

        def get_by_role(self, _role: str, name: str = "") -> FakeLocator:
            return FakeLocator()

        def wait_for_timeout(self, _ms: int) -> None:
            pass

    portal = InterhypPortal()
    portal.ausstattung_klasse_gewaehlt = "einfach"

    # parse_marktwert override: Standard-Schema-Felder
    mw = portal.parse_marktwert(body, FakePage())
    assert mw == {"min": 157000, "mittel": 183000, "max": 207000}

    # extract_extra: nur Interhyp-Extras, KEINE marktwert_eur_*-Felder mehr
    extra = portal.extract_extra(body, FakePage())
    assert "marktwert_eur_min" not in extra
    assert "marktwert_eur_mittel" not in extra
    assert "marktwert_eur_max" not in extra
    assert extra["eur_per_qm"] == 2288
    assert extra["eur_per_qm_gehoben"] == 2425
    assert extra["eur_per_qm_luxus"] == 2688
    assert extra["marktwert_einfach_eur"] == 183000
    assert extra["ausstattung_klasse_gewaehlt"] == "einfach"
    # Keine Trend-Felder
    assert "trend_2j_richtung" not in extra
    assert "wertentwicklung_pct" not in extra


def test_interhyp_datensatz_field_sanierungsjahr_letztes_exists() -> None:
    from core.datensatz import GeneralisierterDatensatz

    d = GeneralisierterDatensatz(
        strasse="X",
        hausnr="1",
        plz="00000",
        ort="Y",
        baujahr=2000,
        zustand="gut",
        ausstattung="normal",
        anzahl_we=1,
        avg_wohnflaeche_qm=80,
        avg_zimmer=3,
        sanierungsjahr_letztes=2020,
    )
    assert d.sanierungsjahr_letztes == 2020
