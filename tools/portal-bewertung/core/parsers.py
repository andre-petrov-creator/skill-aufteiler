"""Portal-agnostische Regex-Parser für Marktwerte, Trends und Ampel-Logik.

Alle Funktionen arbeiten auf reinem Text (üblicherweise `frame.inner_text()`-
Output) und kennen keine Portal-Spezifika. Portal-Adapter rufen sie nach dem
Auslesen der Ergebnisseite.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional


def _euro_to_int(s: str) -> Optional[int]:
    digits = re.sub(r"[.\s]", "", s)
    return int(digits) if digits.isdigit() else None


def parse_marktwert_block(text: str) -> dict[str, Optional[int]]:
    """Extrahiert Mittelwert + Spanne aus einem 'Marktwertermittlung'-Textblock.

    Erwartetes Format (mit Newlines, Pipes oder Spaces zwischen Labels und Zahlen):
      Marktwert ... 173.000 €
      Marktwertspanne ... 168.000 - 178.000 €
    """
    mittel = None
    min_v = None
    max_v = None

    m_mittel = re.search(r"Marktwert[\s\n|]+(\d{1,3}(?:[.\s]\d{3})+)\s*€", text)
    if m_mittel:
        mittel = _euro_to_int(m_mittel.group(1))

    m_spanne = re.search(
        r"Marktwertspanne[\s\n|]+(\d{1,3}(?:[.\s]\d{3})+)[\s\n|]*-?[\s\n|]*"
        r"(\d{1,3}(?:[.\s]\d{3})+)\s*€",
        text,
    )
    if m_spanne:
        min_v = _euro_to_int(m_spanne.group(1))
        max_v = _euro_to_int(m_spanne.group(2))

    return {"min": min_v, "max": max_v, "mittel": mittel}


def parse_trends(text: str) -> dict[str, Optional[float]]:
    """Extrahiert die drei Trend-Prozente aus dem Zeitverlauf-Block.

    Sucht nach drei Trend-Labels und nimmt jeweils den letzten Prozent-Wert
    *vor* dem Label-Match:

      'In den letzten 3 Jahren'    → jahre_3
      'Seit letztem Jahr'          → jahr_1
      'Prognose für das nächste Jahr' → prognose

    Negative Prozente werden korrekt erkannt.
    """
    out: dict[str, Optional[float]] = {"jahre_3": None, "jahr_1": None, "prognose": None}

    labels = [
        ("jahre_3", re.compile(r"(?:In\s+den\s+)?letzten\s+3\s+Jahren?", re.IGNORECASE)),
        ("jahr_1", re.compile(r"Seit\s+letztem\s+Jahr", re.IGNORECASE)),
        ("prognose", re.compile(r"Prognose\s+f[uü]r\s+das\s+n[aä]chste\s+Jahr", re.IGNORECASE)),
    ]
    percent_pat = re.compile(r"([+-])?\s*\|?\s*(\d+[,.]?\d*)\s*%")

    for key, label_re in labels:
        m = label_re.search(text)
        if not m:
            continue
        before = text[: m.start()]
        percents = list(percent_pat.finditer(before))
        if not percents:
            continue
        last = percents[-1]
        sign = (last.group(1) or "").strip()
        num = last.group(2)
        value = float(num.replace(",", "."))
        if sign == "-":
            value = -value
        out[key] = value

    return out


def trend_ampel(
    trends: dict[str, Optional[float]],
    dom_colors: Optional[dict[str, Optional[str]]] = None,
) -> tuple[str, str]:
    """Liefert `(ampel, label)` aus Trend-Werten + optionalem Portal-DOM-Override.

    Schwellen (eigene Heuristik):
      ROT   = Prognose negativ ODER (jahr_1 < 0 UND jahre_3 < 0)
      GELB  = stagnierend: |3J| < 2% und |1J| < 1.5%, oder Prognose ≤ 1%
      GRÜN  = sonst (überwiegend positiv)

    Wenn `dom_colors` Werte enthält, überschreibt der Mehrheitsentscheid der
    Portal-eigenen Farbsignale unsere Heuristik (Quervalidierung).
    """
    j3 = trends.get("jahre_3")
    j1 = trends.get("jahr_1")
    pg = trends.get("prognose")

    if dom_colors:
        votes = [c for c in dom_colors.values() if c]
        if votes:
            top, _ = Counter(votes).most_common(1)[0]
            labels = {
                "gruen": "steigend (Portal-DOM)",
                "gelb": "stagnierend (Portal-DOM)",
                "rot": "fallend (Portal-DOM)",
            }
            return top, labels[top]

    if pg is not None and pg < 0:
        return "rot", "fallend (Prognose negativ)"
    if j1 is not None and j3 is not None and j1 < 0 and j3 < 0:
        return "rot", "fallend (1-J + 3-J negativ)"

    stagnant = (
        j3 is not None
        and abs(j3) < 2.0
        and j1 is not None
        and abs(j1) < 1.5
    ) or (pg is not None and pg <= 1.0)
    if stagnant:
        return "gelb", "stagnierend"

    return "gruen", "steigend"


def build_trend_label(
    *,
    marktwert: dict[str, Optional[int]],
    trends: dict[str, Optional[float]],
    ampel: str,
    ampel_label: str,
) -> str:
    """Baut eine menschenlesbare Zusammenfassung — OHNE Portal-Prefix.

    Der Portal-Name wird im Output-JSON separat als `portal` geführt;
    Konsumenten (Modul 5 PDF) kombinieren beide nach eigenem Layout.
    """
    parts: list[str] = []
    if marktwert.get("min") and marktwert.get("max"):
        parts.append(
            f"Marktwert {marktwert['min']:,} – {marktwert['max']:,} €".replace(",", ".")
        )
    if marktwert.get("mittel"):
        parts.append(f"(Mittel {marktwert['mittel']:,} €)".replace(",", "."))
    emoji = {"gruen": "🟢", "gelb": "🟡", "rot": "🔴"}.get(ampel, "")
    parts.append(f"Trend {emoji} {ampel_label}".strip())
    detail: list[str] = []
    if trends.get("jahre_3") is not None:
        detail.append(f"{trends['jahre_3']:+.1f}% 3J")
    if trends.get("jahr_1") is not None:
        detail.append(f"{trends['jahr_1']:+.1f}% 1J")
    if trends.get("prognose") is not None:
        detail.append(f"{trends['prognose']:+.1f}% Prognose")
    if detail:
        parts.append("(" + " / ".join(detail) + ")")
    return " ".join(parts)
