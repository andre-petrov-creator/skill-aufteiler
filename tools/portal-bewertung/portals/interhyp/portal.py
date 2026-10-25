"""Interhyp-Portal-Adapter.

Architektur: 9-Schritt-Wizard, der vom Adapter selbst durchgeklickt wird
(fill_form). Nach 'Ergebnisse anzeigen' liegt das Resultat im Hauptdokument
(kein iframe). Marktwert + EUR/m² werden aus dem Zusammenfassung-Tab geparst.

Output:
- Standard-Schema (Top-Level via parse_marktwert-Override):
    marktwert_eur_min/mittel/max — Schätzwert + Range
- RunResult.extra (Interhyp-spezifisch):
    eur_per_qm (zur gewaehlten Ausstattung) + eur_per_qm_einfach/gehoben/luxus
    marktwert_einfach_eur/gehoben_eur/luxus_eur
    ausstattung_klasse_gewaehlt

Trend-Auswertung wurde bewusst ausgeklammert — Modul 0 / Modul 5 nutzen
falls noetig externe Trend-Quellen (z.B. CHECK24-3J-Trend).

Live-Lauf: siehe docs/portal-interhyp.md.
"""
from __future__ import annotations

from typing import Any, Optional

from core.datensatz import GeneralisierterDatensatz
from core.portal_base import PortalBase, RunConfig

from . import selectors as sel
from .parsers import (
    parse_eur_per_qm_by_ausstattung,
    parse_marktwert_by_ausstattung,
    parse_marktwert_interhyp,
)


# ---------------------------------------------------------------------------
# Selector-Helpers — robuste Multi-Strategie-Locators fuer Interhyp's
# Material-UI-Style-Wizard (Floating-Labels, Karten-Radios, Footer-Buttons
# mit gleichem Text wie Wizard-Optionen).
# ---------------------------------------------------------------------------

_FILL_STRATEGIES = (
    "label_exact",
    "label_fuzzy",
    "placeholder",
    "aria_label_contains",
)

_CLICK_STRATEGIES = (
    "label_text",
    "role_radio",
    "button_text",
    "role_button",
)


def _fill_input(page: Any, label_text: str, value: str) -> bool:
    """Versucht ein Input zu fuellen ueber mehrere Selektor-Strategien."""
    candidates = [
        ("label_exact", lambda: page.get_by_label(label_text, exact=True)),
        ("label_fuzzy", lambda: page.get_by_label(label_text)),
        ("placeholder", lambda: page.get_by_placeholder(label_text)),
        (
            "aria_label_contains",
            lambda: page.locator(f'input[aria-label*="{label_text}"]'),
        ),
    ]
    for _, make_loc in candidates:
        try:
            loc = make_loc().first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(value, timeout=4_000)
                return True
        except Exception:
            continue
    return False


def _click_text(page: Any, text: str) -> bool:
    """Klickt ein Element mit gegebenem Text ueber mehrere Strategien.

    Reihenfolge: Wizard-spezifische Selektoren (label/radio) zuerst, damit
    keine Footer-Buttons mit dem gleichen Label getroffen werden.
    """
    candidates = [
        ("label_text", lambda: page.locator(f'label:has-text("{text}")')),
        ("role_radio_text", lambda: page.locator(f'[role="radio"]:has-text("{text}")')),
        ("button_text", lambda: page.locator(f'button:has-text("{text}")')),
        ("role_radio", lambda: page.get_by_role("radio", name=text)),
        ("role_button", lambda: page.get_by_role("button", name=text)),
    ]
    for _, make_loc in candidates:
        try:
            loc = make_loc().first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3_000)
                return True
        except Exception:
            continue
    return False


def _click_sanierung_radio(page: Any, value: str) -> bool:
    """Klickt die Wizard-Karte 'Ja' oder 'Nein' fuer 'Hat eine Sanierung
    stattgefunden?'.

    Schutz vor dem Footer-Button 'Sind Sie zufrieden? Ja/Nein' via
    `:not(:has-text("zufrieden"))`.
    """
    for sel_str in [
        f'label:has-text("{value}"):not(:has-text("zufrieden"))',
        f'[role="radio"]:has-text("{value}")',
    ]:
        try:
            loc = page.locator(sel_str).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3_000)
                return True
        except Exception:
            continue
    return False


def _click_strasse_dropdown_item(page: Any, strasse: str, ort: str) -> bool:
    """Klickt im Autocomplete-Dropdown den Eintrag mit Strasse + Ort.

    Interhyp's Strassen-Autocomplete erfordert Klick (Enter reicht nicht).
    Format: 'Prosperstrasse, Essen' (Strasse + Komma + Ort).
    """
    target = f"{strasse}, {ort}"
    for sel_str in [
        f'li:has-text("{target}")',
        f'[role="option"]:has-text("{target}")',
        f'text="{target}"',
    ]:
        try:
            loc = page.locator(sel_str).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2_000)
                return True
        except Exception:
            continue
    # Fallback: erster Vorschlag mit der Strasse
    for sel_str in [f'li:has-text("{strasse}")', f'[role="option"]:has-text("{strasse}")']:
        try:
            loc = page.locator(sel_str).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2_000)
                return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class InterhypPortal(PortalBase):
    """Adapter fuer interhyp.de/rechner/immobilienbewertung."""

    NAME = "interhyp"
    START_URL = sel.START_URL
    COOKIE_ACCEPT_CANDIDATES = sel.COOKIE_ACCEPT_CANDIDATES
    COOKIE_WRAPPER = sel.COOKIE_WRAPPER
    SUBMIT_SELECTOR = ""  # fill_form klickt selbst 'Ergebnisse anzeigen'
    RESULT_FRAME_MARKER = sel.RESULT_FRAME_MARKER

    def __init__(
        self,
        *,
        balkon_groesse_default_qm: int = 6,
        parkplatz_groesse_default_qm: int = 12,
    ) -> None:
        self.balkon_groesse_default_qm = balkon_groesse_default_qm
        self.parkplatz_groesse_default_qm = parkplatz_groesse_default_qm
        self.ausstattung_klasse_gewaehlt: Optional[str] = None

    def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
        """Klickt durch den 9-Schritt-Wizard inkl. 'Ergebnisse anzeigen'."""
        # Step 1: Immobilienart
        _click_text(page, sel.STEP1_IMMOBILIENART)
        page.wait_for_timeout(1_500)

        # Step 2: Adresse (PLZ -> Ort auto, Strasse mit Autocomplete-Klick, Hausnr)
        _fill_input(page, "PLZ", d.plz)
        page.wait_for_timeout(1_500)
        _fill_input(page, "Straße", d.strasse)
        page.wait_for_timeout(1_500)
        _click_strasse_dropdown_item(page, d.strasse, d.ort)
        page.wait_for_timeout(400)
        if d.hausnr:
            _fill_input(page, "Hausnummer", d.hausnr)
            page.wait_for_timeout(400)
        _click_text(page, "Weiter")
        page.wait_for_timeout(1_800)

        # Step 3: Beweggrund (Kapitalanlage, Auto-Advance)
        _click_text(page, sel.STEP3_BEWEGGRUND)
        page.wait_for_timeout(1_800)

        # Step 4: Kaufpreis + Miete — beide leer lassen (haben laut User keinen
        # Einfluss auf die Bewertung). Direkt Weiter.
        _click_text(page, "Weiter")
        page.wait_for_timeout(1_800)

        # Step 5: Wohnflaeche + Zimmer
        _fill_input(page, "Wohnfläche", str(d.avg_wohnflaeche_qm))
        page.wait_for_timeout(300)
        _fill_input(page, "Anzahl der Zimmer", str(d.avg_zimmer))
        page.wait_for_timeout(300)
        _click_text(page, "Weiter")
        page.wait_for_timeout(1_800)

        # Step 6: Baujahr
        _fill_input(page, "Baujahr", str(d.baujahr))
        page.wait_for_timeout(300)
        _click_text(page, "Weiter")
        page.wait_for_timeout(1_800)

        # Step 7: Sanierung Ja/Nein (+ optional Jahr)
        if d.sanierungsjahr_letztes is not None:
            _click_sanierung_radio(page, "Ja")
            page.wait_for_timeout(1_000)
            _fill_input(
                page, "Jahr der letzten Sanierung", str(d.sanierungsjahr_letztes)
            )
            page.wait_for_timeout(400)
        else:
            _click_sanierung_radio(page, "Nein")
            page.wait_for_timeout(800)
        _click_text(page, "Weiter")
        page.wait_for_timeout(1_800)

        # Step 8: Ausstattung (Auto-Advance)
        ausstattung_label = sel.STEP8_AUSSTATTUNG_MAP.get(d.ausstattung, "Einfach")
        self.ausstattung_klasse_gewaehlt = ausstattung_label.lower()
        _click_text(page, ausstattung_label)
        page.wait_for_timeout(2_000)

        # Step 9: Weitere Ausstattung (Checkboxen, optional)
        if d.hat_garage or d.hat_aussenstellplatz:
            _click_text(page, "Parkplatz")
            page.wait_for_timeout(600)
            # Groesse-Feld ist optional; falls vorhanden, fuellen
            _fill_input(
                page, "Größe des Parkplatzes",
                str(self.parkplatz_groesse_default_qm),
            )
            page.wait_for_timeout(300)

        # Submit: 'Ergebnisse anzeigen' (kein 'Weiter')
        _click_text(page, sel.SUBMIT_TEXT_WIZARD)
        page.wait_for_timeout(5_000)

    def dismiss_post_submit_modals(self, page: Any) -> None:
        """Keine Post-Submit-Modals bei Interhyp."""
        return None

    def parse_marktwert(
        self, body_text: str, page: Any
    ) -> dict[str, Optional[int]]:
        """Interhyp-spezifischer Marktwert-Parser (Schätzwert + Range).

        Anders als CHECK24 ('Marktwert ... 173.000 €') liefert Interhyp das
        Range-Layout 'Untergrenze\\nObergrenze\\nSchätzwert *\\nMittel'.
        """
        return parse_marktwert_interhyp(body_text)

    def extract_extra(self, body_text: str, page: Any) -> dict[str, Any]:
        """Parst EUR/m² + Ausstattungs-Tabelle aus dem Zusammenfassung-Tab-Body.

        Marktwert-Min/Mittel/Max liegen im Standard-Schema-Top-Level
        (siehe parse_marktwert). Hier nur die Interhyp-spezifischen Extras.
        """
        eur_per_qm = parse_eur_per_qm_by_ausstattung(body_text)
        marktwert_by_klasse = parse_marktwert_by_ausstattung(body_text)

        klasse = self.ausstattung_klasse_gewaehlt or "einfach"
        chosen_eur_per_qm = eur_per_qm.get(klasse)

        return {
            "eur_per_qm": chosen_eur_per_qm,
            "eur_per_qm_einfach": eur_per_qm["einfach"],
            "eur_per_qm_gehoben": eur_per_qm["gehoben"],
            "eur_per_qm_luxus": eur_per_qm["luxus"],
            "marktwert_einfach_eur": marktwert_by_klasse["einfach"],
            "marktwert_gehoben_eur": marktwert_by_klasse["gehoben"],
            "marktwert_luxus_eur": marktwert_by_klasse["luxus"],
            "ausstattung_klasse_gewaehlt": klasse,
        }


