# `core/datensatz.py` — Generalisierter Datensatz

## Zweck

Zentrale, **portal-agnostische** Datenstruktur, die alle Portal-Adapter konsumieren.
Modul 0 des Aufteilers befüllt sie aus der WE-Liste, der Runner reicht sie weiter
an `Check24Portal`, `HomedayPortal`, etc.

Idee: **Ein Datensatz, viele Portale.** MFH-Durchschnitts-WE-Logik (Wohnfläche,
Zimmer, Bäder, 50%-Garage-Regel) ist hier einmal definiert und gilt für alle
Adapter identisch.

## Files

- [core/datensatz.py](../core/datensatz.py) — Datenklasse + Factories + Helpers
- [tests/test_core_datensatz.py](../tests/test_core_datensatz.py) — 14 Unit-Tests

## Schnittstellen

### Konstanten

```python
ZUSTAND_VALUES = ("renovierungsbeduerftig", "gut", "neu")
AUSSTATTUNG_VALUES = ("einfach", "normal", "gehoben", "luxus")
```

### Dataclass

```python
@dataclass
class GeneralisierterDatensatz:
    strasse: str
    hausnr: str
    plz: str
    ort: str
    baujahr: int
    zustand: str             # ZUSTAND_VALUES
    ausstattung: str         # AUSSTATTUNG_VALUES
    anzahl_we: int           # >= 1
    avg_wohnflaeche_qm: int
    avg_zimmer: int          # >= 1
    avg_badezimmer: int = 1
    hat_garage: bool = False
    hat_aussenstellplatz: bool = False
```

`__post_init__` validiert `zustand`, `ausstattung` und `anzahl_we >= 1`.

### Factories

```python
from_summary(*, strasse, hausnr, plz, ort, baujahr, zustand, ausstattung,
             anzahl_we, gesamtwohnflaeche_qm, gesamtzimmer,
             anzahl_garagen=0, anzahl_aussenstellplaetze=0,
             avg_badezimmer=1) -> GeneralisierterDatensatz
```

→ aus aggregierten Summen rechnen (häufiger Quick-Check-Fall in Modul 0).

```python
from_lists(*, strasse, hausnr, plz, ort, baujahr, zustand, ausstattung,
           wohnflaechen_qm, zimmer_liste, badezimmer_liste=None,
           anzahl_garagen=0, anzahl_aussenstellplaetze=0) -> GeneralisierterDatensatz
```

→ aus Einzel-WE-Listen rechnen (genauerer Modul-1-Fall, sobald WE-Daten extrahiert).

### Helpers

- `round_half_up(x: float) -> int` — `math.floor(x + 0.5)`, also 0.5 rundet aufwärts
- `avg_int(values: list[float]) -> int` — Durchschnitt + `round_half_up`
- `avg_zimmer(values: list[float]) -> int` — wie `avg_int`, aber min. 1

## Berechnungsregeln

| Wert | Regel |
|---|---|
| Ø Wohnfläche | arithmetisches Mittel der WE-Flächen, `round_half_up` |
| Ø Zimmer | arithmetisches Mittel der Zimmerzahlen, `round_half_up`, min. 1 |
| Ø Badezimmer | aus `badezimmer_liste` gerechnet, sonst Default 1 |
| Hat Garage | `(anzahl_garagen / anzahl_we) >= 0.5` |
| Hat Außenstellplatz | `(anzahl_aussenstellplaetze / anzahl_we) >= 0.5` |

### Beispiele

**Quick-Check (`from_summary`):** 4 WE, 320 qm gesamt, 12 Zimmer gesamt, 2 Garagen
→ `avg_wohnflaeche_qm=80`, `avg_zimmer=3`, `hat_garage=True` (2/4 = 0.5).

**Modul 1 (`from_lists`):** WE-Liste `[60, 70, 80, 90]` qm, Zimmer `[2, 3, 3, 4]`,
Bäder `[1, 1, 1, 2]` → `avg_wohnflaeche_qm=75`, `avg_zimmer=3`, `avg_badezimmer=1`.

**Garage unter Schwelle:** 1 Garage bei 3 WE → 1/3 ≈ 0.33 < 0.5 → `hat_garage=False`.

## Bekannte Limitierungen / Designentscheidungen

- **Badezimmer-Default 1.** Die Gäste-WC-Logik („wenn ≥50% der WE ein Gäste-WC
  haben, dann avg_badezimmer = 2") gehört **nicht** in dieses Modul, sondern
  in Modul 0 des Aufteilers. Dieses File ist ein dummer Datenträger.
- **Keine Portal-Logik.** Adresse-Normalisierung (z.B. „Straße" → „Str." für
  CHECK24-Autocomplete) gehört in den Portal-Adapter, nicht hier.
- **`round_half_up` ist nicht banker's rounding.** Exakte 0.5 rundet nach oben
  (1.5 → 2, 2.5 → 3). Bewusste Entscheidung: matched die Erwartung der Portale
  („so viele Zimmer hat die durchschnittliche WE").
- **Negative Werte bei `round_half_up`:** -1.5 → -1 (rundet Richtung Null wegen
  `math.floor`). In der Praxis treten negative Werte nicht auf — getestet zur
  Dokumentation des Verhaltens.

## Tests

Default-Run: `pytest tests/test_core_datensatz.py -v` — 14 grüne Tests:
round_half_up (3×), avg_zimmer (3×), from_summary (2×), from_lists, garage_50%,
invalid_zustand, invalid_ausstattung, list_mismatch, constants_exported.
