"""Abstrakte Portal-Klasse + Run-Config + Run-Result.

Jeder konkrete Portal-Adapter (portals/check24/portal.py, portals/homeday/...)
erbt von `PortalBase`, definiert seine Selektoren als Klassen-Konstanten und
implementiert `fill_form()`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from core.browser import BrowserConfig


@dataclass
class RunConfig:
    """Konfiguration für einen Portal-Lauf."""

    headless: bool = False
    verbose: bool = False
    kaufabsicht: str = "kauf"  # "kauf" oder "verkauf" — vom Portal interpretiert
    browser: BrowserConfig = field(default_factory=BrowserConfig)


@dataclass
class RunResult:
    """Ergebnis-Container, schema-konform laut DEVELOPMENT_GUIDELINES.md."""

    status: str  # "ok" | "error"
    portal: str
    marktwert_eur_min: Optional[int] = None
    marktwert_eur_max: Optional[int] = None
    marktwert_eur_mittel: Optional[int] = None
    trends: dict[str, Optional[float]] = field(
        default_factory=lambda: {"jahre_3": None, "jahr_1": None, "prognose": None}
    )
    trend_ampel: Optional[str] = None
    trend_ampel_label: Optional[str] = None
    trend_label: Optional[str] = None
    url: str = ""
    timestamp: str = ""
    screenshot_path: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_text_excerpt: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status": self.status,
            "portal": self.portal,
            "marktwert_eur_min": self.marktwert_eur_min,
            "marktwert_eur_max": self.marktwert_eur_max,
            "marktwert_eur_mittel": self.marktwert_eur_mittel,
            "trends": self.trends,
            "trend_ampel": self.trend_ampel,
            "trend_ampel_label": self.trend_ampel_label,
            "trend_label": self.trend_label,
            "url": self.url,
            "timestamp": self.timestamp,
            "screenshot_path": self.screenshot_path,
        }
        if self.status == "error":
            out["error_code"] = self.error_code
            out["error_message"] = self.error_message
        if self.raw_text_excerpt is not None:
            out["raw_text_excerpt"] = self.raw_text_excerpt
        if self.extra:
            out["extra"] = self.extra
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class PortalBase:
    """Basis für alle Portal-Adapter.

    Konkrete Adapter überschreiben:
      - Klassen-Konstanten (NAME, START_URL, COOKIE_*, SUBMIT_SELECTOR,
        RESULT_FRAME_MARKER)
      - `fill_form(page, datensatz, cfg)`
      - optional: `dismiss_post_submit_modals(page)` (Default: kein-op)
      - optional: `extract_dom_colors(page)` (Default: leeres Dict)
    """

    NAME: str = "base"
    START_URL: str = ""
    COOKIE_ACCEPT_CANDIDATES: list[str] = []
    COOKIE_WRAPPER: str = ""
    SUBMIT_SELECTOR: str = ""
    RESULT_FRAME_MARKER: str = ""

    def fill_form(self, page: Any, datensatz: Any, cfg: RunConfig) -> None:
        raise NotImplementedError("Subclass must implement fill_form()")

    def dismiss_post_submit_modals(self, page: Any) -> None:
        """Hook für Modals nach Submit (Topzinsen, zweites Cookie-Banner ...).

        Default: nichts. Subklassen überschreiben bei Bedarf.
        """
        return None

    def extract_dom_colors(self, page: Any) -> dict[str, Optional[str]]:
        """Hook für portal-spezifische Trend-Farben aus dem DOM.

        Default: leeres Dict (keine DOM-Override für `trend_ampel`).
        """
        return {}

    def extract_extra(self, body_text: str, page: Any) -> dict[str, Any]:
        """Hook für portal-spezifische Zusatz-Felder, die NICHT ins Standard-Schema
        passen (z.B. Homeday €/m² + Wohnlage). Landet im `RunResult.extra`-Slot.

        Default: leeres Dict.
        """
        return {}

    def parse_marktwert(
        self, body_text: str, page: Any
    ) -> dict[str, Optional[int]]:
        """Hook für Portal-spezifische Marktwert-Extraktion.

        Default: nutzt `core.parsers.parse_marktwert_block` (CHECK24-Layout).
        Subklassen mit anderem Body-Format (z.B. Interhyp) überschreiben mit
        eigenem Parser. Returnt `{"min", "mittel", "max"}` (alle Optional[int]).
        """
        from core.parsers import parse_marktwert_block

        return parse_marktwert_block(body_text)
