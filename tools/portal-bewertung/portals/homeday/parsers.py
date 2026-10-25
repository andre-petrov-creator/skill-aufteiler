"""Body-Text-Parser für die Homeday-Preisatlas-Result-Seite.

Extrahiert:
- €/m² aus "Ø 1.700 €/m²"-Pattern
- 12-Monats-Trend für Stadt + Wohnblock
- Wohnblock-Wohnlage-Label (einfach/mittel/gut/sehr gut/herausragend)

Plus Ampel-Logik für Trend-% (gleiche Schwellen wie core.parsers, aber
explizit hier dupliziert, weil Homeday nur eine Zahl pro Bezug liefert,
keine Mehrfach-Werte wie CHECK24).
"""
from __future__ import annotations

import re
from typing import Optional

# Aus der Wohnlage-Legende (5 Stufen, einfach → herausragend):
#   einfach (gelb), mittel (orange), gut (rot), sehr gut (dunkelrot), herausragend (lila)
# Farbwerte ausgewählt um zur Homeday-Legende zu passen.
WOHNLAGE_FARBE_MAP: dict[str, str] = {
    "einfach": "#FFE873",       # hellgelb
    "mittel": "#F7A823",        # orange
    "gut": "#F76923",           # rot-orange
    "sehr gut": "#C8312B",      # rot
    "herausragend": "#7B2D8E",  # lila
}

WOHNLAGE_LABELS = list(WOHNLAGE_FARBE_MAP.keys())


def parse_eur_per_qm(text: str) -> Optional[int]:
    """Liest '⌀ 1.700 €/m²' → 1700. Tausenderpunkt + Komma-Dezimal toleriert."""
    m = re.search(r"Ø\s*(\d{1,3}(?:\.\d{3})*)(?:,\d+)?\s*€/m²", text)
    if not m:
        return None
    digits = m.group(1).replace(".", "")
    return int(digits) if digits.isdigit() else None


def _parse_percent(s: str) -> Optional[float]:
    """'+6 %' → 6.0, '-1,8 %' → -1.8, '—' → None."""
    s = s.strip()
    if s in ("—", "-", "k.A.", ""):
        return None
    m = re.match(r"([+-]?\s*\d+(?:[,.]\d+)?)\s*%", s)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_trend_12m(text: str) -> dict[str, Optional[float]]:
    """Extrahiert Stadt- und Wohnblock-Wert aus dem 12-Monats-Block.

    Pattern (Body-Text aus der Result-Seite):
      PREISTREND ÜBER 12 MONATE
      Stadt
      +6 %
      Wohnblock
      —

    Beide Werte können fehlen oder '—' sein.
    """
    out: dict[str, Optional[float]] = {"stadt": None, "wohnblock": None}

    block_match = re.search(
        r"PREISTREND\s+ÜBER\s+12\s+MONATE(.*?)(?:Preisverlauf|Wohnlage|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return out
    block = block_match.group(1)

    stadt_match = re.search(
        r"Stadt\s*[\r\n]+\s*([+-]?\s*[\d.,]+\s*%|—|k\.A\.)",
        block,
        re.IGNORECASE,
    )
    if stadt_match:
        out["stadt"] = _parse_percent(stadt_match.group(1))

    wb_match = re.search(
        r"Wohnblock\s*[\r\n]+\s*([+-]?\s*[\d.,]+\s*%|—|k\.A\.)",
        block,
        re.IGNORECASE,
    )
    if wb_match:
        out["wohnblock"] = _parse_percent(wb_match.group(1))

    return out


def parse_wohnblock_wohnlage(text: str) -> Optional[str]:
    """Extrahiert das Wohnlage-Label des spezifischen Wohnblocks.

    Pattern: 'Wohnlage\\n<Label>\\n' wobei <Label> einer von
    einfach/mittel/gut/sehr gut/herausragend ist (case-insensitive).
    """
    m = re.search(
        r"Wohnlage\s*[\r\n]+\s*(Einfach|Mittel|Gut|Sehr\s+gut|Herausragend)\b",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    label = re.sub(r"\s+", " ", m.group(1).strip().lower())
    return label if label in WOHNLAGE_FARBE_MAP else None


def wohnlage_farbe(label: Optional[str]) -> Optional[str]:
    """Liefert den Hex-Farbcode zum Wohnlage-Label, sonst None."""
    if not label:
        return None
    return WOHNLAGE_FARBE_MAP.get(label.lower())


def trend_ampel_homeday(trend_pct: Optional[float]) -> tuple[str, str]:
    """Ampel-Logik nach User-Vorgabe — auf 12-Monats-Trend angewendet.

    Schwellen:
      > +1 %    → grün ("steigend")
      |x| <= 1  → gelb ("stagnierend")
      < -1 %    → rot ("fallend")
      None      → grau ("keine Daten")
    """
    if trend_pct is None:
        return "grau", "— (keine Daten)"
    if trend_pct > 1.0:
        return "gruen", f"steigend (+{trend_pct:.1f}%)"
    if trend_pct < -1.0:
        return "rot", f"fallend ({trend_pct:+.1f}%)"
    return "gelb", f"stagnierend ({trend_pct:+.1f}%)"
