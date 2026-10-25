"""Homeday-Portal-Adapter.

Architektur-Eigenheit: Homeday hat einen Deep-Link, der das Formular
überspringt. Adapter navigiert direkt zur Result-URL — kein fill_form-Schritt
nötig. Die Standard-PortalBase.fill_form-API bleibt für das Framework
erfüllt, ist aber ein No-Op.

Werte-Extraktion: Body-Text + Regex (homeday/parsers.py). Output-Schema
wird im `RunResult.extra`-Slot erweitert:
  eur_per_qm, wohnblock_wohnlage, wohnblock_farbe,
  trend_12m_stadt_pct, trend_12m_stadt_ampel, trend_12m_stadt_ampel_label,
  trend_12m_wohnblock_pct, trend_12m_wohnblock_ampel, trend_12m_wohnblock_ampel_label.

Marktwert-Felder (marktwert_eur_min/max/mittel + trends) bleiben None,
weil Homeday keine absoluten Marktwerte liefert. Modul 0 / Modul 5
konsumiert das `extra`-Dict separat (siehe docs/portal-homeday.md).
"""
from __future__ import annotations

from typing import Any, Optional

from core.datensatz import GeneralisierterDatensatz
from core.portal_base import PortalBase, RunConfig

from . import selectors as sel
from .parsers import (
    parse_eur_per_qm,
    parse_trend_12m,
    parse_wohnblock_wohnlage,
    trend_ampel_homeday,
    wohnlage_farbe,
)


class HomedayPortal(PortalBase):
    NAME = "homeday"
    START_URL = sel.START_URL
    COOKIE_ACCEPT_CANDIDATES = sel.COOKIE_ACCEPT_CANDIDATES
    COOKIE_WRAPPER = sel.COOKIE_WRAPPER
    SUBMIT_SELECTOR = ""  # kein Submit — Deep-Link statt Form
    RESULT_FRAME_MARKER = sel.RESULT_FRAME_MARKER

    def __init__(
        self,
        *,
        marketing_type: str = "sell",
        property_type: str = "apartment",
    ) -> None:
        self.marketing_type = marketing_type
        self.property_type = property_type

    def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
        """Statt Formular zu befüllen, navigieren wir direkt zur Result-URL."""
        result_url = sel.build_result_url(
            strasse=d.strasse,
            hausnr=d.hausnr,
            plz=d.plz,
            ort=d.ort,
            marketing_type=self.marketing_type,
            property_type=self.property_type,
        )
        page.goto(result_url, wait_until="domcontentloaded")
        page.wait_for_timeout(4_000)

    def dismiss_post_submit_modals(self, page: Any) -> None:
        """Homeday hat keine Post-Submit-Modals — Result ist direkt da."""
        return None

    def extract_extra(self, body_text: str, page: Any) -> dict[str, Any]:
        """Liefert das Homeday-spezifische Datenpaket fürs `RunResult.extra`."""
        return parse_homeday_extras(body_text)


def parse_homeday_extras(body_text: str) -> dict[str, Any]:
    """Erzeugt das `extra`-Dict aus dem Body-Text der Result-Seite.

    Wird vom Runner/Adapter aufgerufen, nachdem `read_frame_body_deep` oder
    `read_page_body_deep` den Text geliefert hat.
    """
    eur_per_qm = parse_eur_per_qm(body_text)
    trends = parse_trend_12m(body_text)
    wohnlage = parse_wohnblock_wohnlage(body_text)

    stadt_ampel, stadt_label = trend_ampel_homeday(trends["stadt"])
    wb_ampel, wb_label = trend_ampel_homeday(trends["wohnblock"])

    return {
        "eur_per_qm": eur_per_qm,
        "wohnblock_wohnlage": wohnlage,
        "wohnblock_farbe_hex": wohnlage_farbe(wohnlage),
        "trend_12m_stadt_pct": trends["stadt"],
        "trend_12m_stadt_ampel": stadt_ampel,
        "trend_12m_stadt_ampel_label": stadt_label,
        "trend_12m_wohnblock_pct": trends["wohnblock"],
        "trend_12m_wohnblock_ampel": wb_ampel,
        "trend_12m_wohnblock_ampel_label": wb_label,
    }
