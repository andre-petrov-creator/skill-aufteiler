"""Generalisierter Datensatz für Immobilien-Bewertungsportale.

Eine zentrale Datenstruktur, die für CHECK24 und später andere Portale
(Sprengnetter, Immowelt, ...) wiederverwendbar ist. Modul 0 des Aufteilers
befüllt sie aus der WE-Liste, das Tool reicht sie an die Portal-Adapter
weiter.

Berechnungslogik (alle generalisierten Werte beziehen sich auf eine
DURCHSCHNITTS-WE im MFH, nicht auf das Gesamthaus):

  Ø Wohnfläche  = arithmetisches Mittel der WE-Flächen, gerundet
  Ø Zimmer      = arithmetisches Mittel der Zimmerzahlen, 0,5 → aufrunden
  Ø Badezimmer  = aus WE-Liste, sonst Default 1 (Standard-MFH).
                   Wenn ein Exposé erkennen lässt, dass ≥50% der WE neben
                   dem Bad ein Gäste-WC haben, gehört das in den Wert (2).
  Garage         = (Anzahl Garagen / Anzahl WE) ≥ 0,5
  Außenstellpl. = (Anzahl Außenstellplätze / Anzahl WE) ≥ 0,5
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


ZUSTAND_VALUES = ("renovierungsbeduerftig", "gut", "neu")
AUSSTATTUNG_VALUES = ("einfach", "normal", "gehoben", "luxus")


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def avg_int(values: list[float]) -> int:
    if not values:
        raise ValueError("Liste darf nicht leer sein")
    return round_half_up(sum(values) / len(values))


def avg_zimmer(values: list[float]) -> int:
    return max(1, avg_int(values))


@dataclass
class GeneralisierterDatensatz:
    strasse: str
    hausnr: str
    plz: str
    ort: str
    baujahr: int
    zustand: str
    ausstattung: str

    anzahl_we: int
    avg_wohnflaeche_qm: int
    avg_zimmer: int
    avg_badezimmer: int = 1

    hat_garage: bool = False
    hat_aussenstellplatz: bool = False

    def __post_init__(self) -> None:
        if self.zustand not in ZUSTAND_VALUES:
            raise ValueError(f"zustand muss {ZUSTAND_VALUES} sein, war {self.zustand!r}")
        if self.ausstattung not in AUSSTATTUNG_VALUES:
            raise ValueError(f"ausstattung muss {AUSSTATTUNG_VALUES} sein, war {self.ausstattung!r}")
        if self.anzahl_we < 1:
            raise ValueError("anzahl_we muss >= 1 sein")


def from_summary(
    *,
    strasse: str,
    hausnr: str,
    plz: str,
    ort: str,
    baujahr: int,
    zustand: str,
    ausstattung: str,
    anzahl_we: int,
    gesamtwohnflaeche_qm: float,
    gesamtzimmer: float,
    anzahl_garagen: int = 0,
    anzahl_aussenstellplaetze: int = 0,
    avg_badezimmer: int = 1,
) -> GeneralisierterDatensatz:
    """Aus aggregierten Summen rechnen (häufiger Quick-Check-Fall)."""
    if anzahl_we < 1:
        raise ValueError("anzahl_we muss >= 1 sein")
    avg_qm = round_half_up(gesamtwohnflaeche_qm / anzahl_we)
    avg_z = max(1, round_half_up(gesamtzimmer / anzahl_we))
    return GeneralisierterDatensatz(
        strasse=strasse,
        hausnr=hausnr,
        plz=plz,
        ort=ort,
        baujahr=baujahr,
        zustand=zustand,
        ausstattung=ausstattung,
        anzahl_we=anzahl_we,
        avg_wohnflaeche_qm=avg_qm,
        avg_zimmer=avg_z,
        avg_badezimmer=avg_badezimmer,
        hat_garage=(anzahl_garagen / anzahl_we) >= 0.5,
        hat_aussenstellplatz=(anzahl_aussenstellplaetze / anzahl_we) >= 0.5,
    )


def from_lists(
    *,
    strasse: str,
    hausnr: str,
    plz: str,
    ort: str,
    baujahr: int,
    zustand: str,
    ausstattung: str,
    wohnflaechen_qm: list[float],
    zimmer_liste: list[float],
    badezimmer_liste: Optional[list[int]] = None,
    anzahl_garagen: int = 0,
    anzahl_aussenstellplaetze: int = 0,
) -> GeneralisierterDatensatz:
    """Aus Einzel-WE-Listen rechnen (genauerer Modul-1-Fall)."""
    if not wohnflaechen_qm or not zimmer_liste:
        raise ValueError("WE-Listen dürfen nicht leer sein")
    if len(wohnflaechen_qm) != len(zimmer_liste):
        raise ValueError(
            f"Listen-Längen unterschiedlich: wohnflaechen={len(wohnflaechen_qm)}, zimmer={len(zimmer_liste)}"
        )
    anzahl_we = len(wohnflaechen_qm)
    avg_bad = avg_int([float(b) for b in badezimmer_liste]) if badezimmer_liste else 1
    return GeneralisierterDatensatz(
        strasse=strasse,
        hausnr=hausnr,
        plz=plz,
        ort=ort,
        baujahr=baujahr,
        zustand=zustand,
        ausstattung=ausstattung,
        anzahl_we=anzahl_we,
        avg_wohnflaeche_qm=avg_int(wohnflaechen_qm),
        avg_zimmer=avg_zimmer(zimmer_liste),
        avg_badezimmer=max(1, avg_bad),
        hat_garage=(anzahl_garagen / anzahl_we) >= 0.5,
        hat_aussenstellplatz=(anzahl_aussenstellplaetze / anzahl_we) >= 0.5,
    )
