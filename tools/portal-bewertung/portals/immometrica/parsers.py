"""Parser fuer die DOM-Body-Texte der Marktstatistik-Page.

Eingabe: body.innerText der Statistik-Page nach 'Statistik erstellen'-Klick.
Ausgabe: strukturierte Stat-Bloecke (Haupt + Zusatzinfo).

Pattern (aus Live-DOM-Dumps):
    Übersicht: Haus kaufen / Wohnung kaufen / Haus mieten / Wohnung mieten
    Anzahl Angebote: <int>
    Median Preis pro m²: <number> €
    Median Onlinezeit in Tagen: <int>
    Rendite: <number> %        (nur bei Kauf)
    Zusatzinfo: Wohnung/Haus mieten / kaufen
    ... (gleiche Felder)
"""
from __future__ import annotations

import re
from typing import Optional


def _parse_int(s: str) -> Optional[int]:
    s = s.strip().replace(".", "").replace(" ", "")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_float_eu(s: str) -> Optional[float]:
    """DE-Zahl mit Tausender-Punkt + Dezimal-Komma → float."""
    s = s.strip().replace(" ", "")
    if not s:
        return None
    # 1.950 → 1950, 9,95 → 9.95, 3.286 → 3286, 13,67 → 13.67
    if "," in s:
        # Komma = Dezimal, Punkt = Tausender
        s = s.replace(".", "").replace(",", ".")
    else:
        # Nur Punkt: könnte Tausender oder Dezimal sein.
        # Heuristik: wenn nach letztem Punkt 1-2 Stellen → Dezimal
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(".", ".")  # bleibt Dezimal
        else:
            s = s.replace(".", "")  # Tausender entfernen
    try:
        return float(s)
    except ValueError:
        return None


_BLOCK_RE = re.compile(
    r"(?:Übersicht|Zusatzinfo):\s*(?P<heading>[^\n]+)\n"
    r"(?P<inner>(?:.|\n){0,400}?)"
    r"(?=(?:Übersicht|Zusatzinfo):|Angebote\s*\(|$)",
    re.MULTILINE,
)

_ANZAHL_RE = re.compile(r"Anzahl\s*Angebote\s*([\d.\s]+)", re.MULTILINE)
_PREIS_RE = re.compile(
    r"Median\s*Preis\s*pro\s*m²\s*([\d.,]+)\s*€", re.MULTILINE
)
_ONLINE_RE = re.compile(
    r"Median\s*Onlinezeit\s*in\s*Tagen\s*(\d+)", re.MULTILINE
)
_RENDITE_RE = re.compile(r"Rendite\s*([\d,]+)\s*%", re.MULTILINE)


def parse_stat_block(body_text: str) -> dict:
    """Parst alle 'Übersicht'- und 'Zusatzinfo'-Bloecke aus dem DOM-Body.

    Returns:
        {
            "uebersicht": {"heading": "Haus kaufen", "anzahl": ..., ...},
            "zusatzinfo": {"heading": "Haus mieten", ...},
        }
        oder leeres Dict wenn nichts gefunden.
    """
    out: dict = {"uebersicht": None, "zusatzinfo": None}

    # Robuste Variante: splitte beim Übersicht/Zusatzinfo-Marker
    # und parse jeden Block einzeln
    blocks = re.split(
        r"(Übersicht:\s*[^\n]+|Zusatzinfo:\s*[^\n]+)",
        body_text,
    )
    # blocks ist [vor_erstem_marker, marker_1, inner_1, marker_2, inner_2, ...]

    current_kind = None
    current_heading = None
    for piece in blocks:
        piece = piece.strip()
        if not piece:
            continue
        m = re.match(r"^(Übersicht|Zusatzinfo):\s*(.+?)$", piece)
        if m:
            current_kind = "uebersicht" if m.group(1) == "Übersicht" else "zusatzinfo"
            current_heading = m.group(2).strip()
            continue
        if current_kind is None:
            continue
        # Innerer Block: parse Werte
        block = {
            "heading": current_heading,
            "anzahl_angebote": None,
            "median_preis_eur_per_qm": None,
            "median_onlinezeit_tage": None,
            "rendite_pct": None,
        }
        m = _ANZAHL_RE.search(piece)
        if m:
            block["anzahl_angebote"] = _parse_int(m.group(1))
        m = _PREIS_RE.search(piece)
        if m:
            block["median_preis_eur_per_qm"] = _parse_float_eu(m.group(1))
        m = _ONLINE_RE.search(piece)
        if m:
            block["median_onlinezeit_tage"] = _parse_int(m.group(1))
        m = _RENDITE_RE.search(piece)
        if m:
            block["rendite_pct"] = _parse_float_eu(m.group(1))
        out[current_kind] = block
        # Reset fuer naechsten Block
        current_kind = None
        current_heading = None

    return out


def parse_geo_state(body_text: str) -> Optional[str]:
    """Liest den aktuell gesetzten Ort-Tag aus dem DOM-Body.

    Pattern aus Live-DOMs: nach 'Im Baum auswählen\\n' steht der gesetzte Ort,
    z.B. 'Essen, Nordrhein-Westfalen' oder '45357 Essen'.
    """
    m = re.search(
        r"Im Baum auswählen\s*\n\s*([^\n]+?)\s*\n", body_text
    )
    if m:
        return m.group(1).strip()
    return None


def extract_year_half_active(body_text: str) -> Optional[str]:
    """Liest den aktiven Halbjahres-Filter aus dem DOM (z.B. 'H1/2026')."""
    # Aktiver Button hat oft .active oder primary CSS; im Body-Text ist's
    # aber nicht direkt sichtbar. Wir suchen nach 'Statistik für: <Wert>'
    # falls vorhanden, sonst None.
    m = re.search(r"Statistik\s*für:\s*([^\n]+)", body_text)
    if m:
        # Format: "Gesamter Zeitraum H1/2018 H2/2018 ... H1/2026"
        # Wir koennen den aktiven nicht aus dem Text bestimmen — Caller
        # uebergibt ihn explizit.
        return None
    return None
