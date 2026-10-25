"""Body-Text-Parser fuer die Interhyp-Immobilienbewertungs-Result-Seite.

Extrahiert:
- Marktwert-Min/Mittel/Max aus 'Untergrenze/Schaetzwert/Obergrenze'-Block
- Marktwert + EUR/m² je Ausstattungsklasse (Einfach/Gehoben/Luxus)

Hinweis: Trend-Auswertung (Wertentwicklungs-Tab) wurde aus dem Adapter
entfernt — siehe portal.py-Modul-Docstring fuer Begruendung.
"""
from __future__ import annotations

import re
from typing import Optional

# Euro-Wert mit Tausenderpunkten, optional vor EUR oder €.
_EURO_INT_RE = r"(\d{1,3}(?:\.\d{3})+)\s*(?:EUR|€)"


def _euro_to_int(s: str) -> Optional[int]:
    digits = s.replace(".", "").replace(" ", "")
    return int(digits) if digits.isdigit() else None


def parse_marktwert_interhyp(text: str) -> dict[str, Optional[int]]:
    """Extrahiert Marktwert-Min/Mittel/Max aus dem Zusammenfassung-Tab.

    Live-Body-Layout (Stand 2026-05-15):
      <Untergrenze-€>
      <Obergrenze-€>
      Schätzwert *
      <Mittel-€>

    Heisst: Min und Max sind nicht beschriftet — sie stehen direkt vor dem
    Schätzwert-Marker. Wir matchen das ganze Block-Pattern als Anker.

    Fallback: einzelner Schätzwert wenn Block-Pattern bricht.

    Toleriert 'EUR' und '€', 'ä' und 'ae' in 'Schätzwert', optional '*'.
    """
    out: dict[str, Optional[int]] = {"min": None, "mittel": None, "max": None}

    # Voll-Pattern: 2 Werte, dann Schätzwert-Marker, dann Mittel-Wert
    m_full = re.search(
        rf"{_EURO_INT_RE}\s*[\r\n]+\s*"
        rf"{_EURO_INT_RE}\s*[\r\n]+\s*"
        rf"Sch(?:ä|ae)tzwert\s*\*?\s*[\r\n]+\s*"
        rf"{_EURO_INT_RE}",
        text,
        re.IGNORECASE,
    )
    if m_full:
        out["min"] = _euro_to_int(m_full.group(1))
        out["max"] = _euro_to_int(m_full.group(2))
        out["mittel"] = _euro_to_int(m_full.group(3))
        return out

    # Legacy-Fallback: explizit beschriftete Werte (Sparring-Sample)
    m_min = re.search(rf"Untergrenze\s*[\r\n]+\s*{_EURO_INT_RE}", text, re.IGNORECASE)
    if m_min:
        out["min"] = _euro_to_int(m_min.group(1))

    m_mittel = re.search(
        rf"Sch(?:ä|ae)tzwert\s*\*?\s*[\r\n]+\s*{_EURO_INT_RE}", text, re.IGNORECASE
    )
    if m_mittel:
        out["mittel"] = _euro_to_int(m_mittel.group(1))

    m_max = re.search(rf"Obergrenze\s*[\r\n]+\s*{_EURO_INT_RE}", text, re.IGNORECASE)
    if m_max:
        out["max"] = _euro_to_int(m_max.group(1))

    return out


def parse_eur_per_qm_by_ausstattung(text: str) -> dict[str, Optional[int]]:
    """Extrahiert EUR/m² je Klasse aus dem 'Preisunterschiede...'-Block.

    Live-Body-Layout (Stand 2026-05-15):
      Einfach 162.000 €
      2.025 € /m²
      Gehoben 172.000 €
      2.150 € /m²
      Luxus 191.000 €
      2.388 € /m²

    Wichtig: Klasse + Marktwert stehen in der SELBEN Zeile (kein Newline
    dazwischen). EUR/m² hat ein Leerzeichen zwischen '€' und '/m²'.

    Auch das Legacy-Layout (Newline zwischen Klasse und Wert) wird matched.
    """
    out: dict[str, Optional[int]] = {"einfach": None, "gehoben": None, "luxus": None}
    eur_per_qm_value = r"(\d{1,3}(?:\.\d{3})*)\s*(?:EUR|€)\s*/\s*m"
    for klasse in ("Einfach", "Gehoben", "Luxus"):
        # Pattern toleriert beide Layouts (Klasse mit Wert in einer Zeile
        # ODER getrennt durch Newline). \s+ matched Leerzeichen UND Newline.
        pattern = (
            rf"(?:^|\n)\s*{klasse}\s+\d{{1,3}}(?:\.\d{{3}})+\s*(?:EUR|€)\s*[\r\n]+"
            rf"\s*{eur_per_qm_value}"
        )
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            out[klasse.lower()] = _euro_to_int(m.group(1))
    return out


def parse_marktwert_by_ausstattung(text: str) -> dict[str, Optional[int]]:
    """Extrahiert den Marktwert (EUR) je Klasse aus dem 'Preisunterschiede...'-Block.

    Live-Pattern: 'Einfach 162.000 €' (Klasse + Wert in einer Zeile).
    Legacy: 'Einfach\\n183.000 EUR' (mit Newline) wird auch matched.
    """
    out: dict[str, Optional[int]] = {"einfach": None, "gehoben": None, "luxus": None}
    for klasse in ("Einfach", "Gehoben", "Luxus"):
        # \s+ erlaubt Leerzeichen ODER Newline zwischen Klasse und Wert
        pattern = rf"(?:^|\n)\s*{klasse}\s+{_EURO_INT_RE}"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            out[klasse.lower()] = _euro_to_int(m.group(1))
    return out
