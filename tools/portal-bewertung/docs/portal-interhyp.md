# `portals/interhyp/` — Interhyp-Immobilienbewertungs-Adapter

## Zweck

Interhyp liefert für eine Adresse einen **Marktwert** (Untergrenze, Schätzwert,
Obergrenze) plus **EUR/m²** je Ausstattungsklasse (Einfach, Gehoben, Luxus).

Anders als CHECK24 (Pipe-Format, iframe) und Homeday (Deep-Link, kein
Marktwert) hat Interhyp einen **9-Schritt-Wizard**, der vom Adapter komplett
durchgeklickt wird (kein Deep-Link). Output: alle Interhyp-Werte landen im
`RunResult.extra`-Slot (Homeday-Pattern), die Standard-Marktwert-Felder
bleiben `null`.

**Hinweis zur Trend-Auswertung:** Die Wertentwicklungs-Linie (Wertentwicklung-Tab)
wird **bewusst nicht** ausgewertet — die letzten 2 Jahre des Charts sind
schwer programmatisch zu interpretieren (Material-UI-Dropdown nicht zuverlässig
klickbar, SVG-Heuristik unscharf). Modul 0 / Modul 5 nutzen falls nötig
externe Trend-Quellen (z.B. CHECK24-3J-Trend).

## Files

- [portals/interhyp/selectors.py](../portals/interhyp/selectors.py) — Konstanten,
  Wizard-Labels, Mapping `ausstattung → Karten-Text`
- [portals/interhyp/parsers.py](../portals/interhyp/parsers.py) — Body-Text-Regex
  + Ampel-Logik
- [portals/interhyp/portal.py](../portals/interhyp/portal.py) — `InterhypPortal`
  (PortalBase-Subklasse), Multi-Strategie-Locators, `fill_form` für alle
  9 Wizard-Steps, `extract_extra` mit Wertentwicklung-Tab-Navigation
- [tests/test_portals_interhyp_parsers.py](../tests/test_portals_interhyp_parsers.py)
  — 18 Parser-Tests
- [tests/test_portals_interhyp_importable.py](../tests/test_portals_interhyp_importable.py)
  — 5 Smoke-Tests

## Architektur-Eigenheiten

### 1. 9-Schritt-Wizard mit Multi-Strategie-Locators

Interhyp nutzt Material-UI-Style-Komponenten (Floating-Labels, Karten-Radios)
plus einen Footer-Bereich „Sind Sie mit dem Rechner zufrieden? Ja/Nein", der
mit Wizard-Karten-Texten kollidieren kann.

Der Adapter probiert pro Element mehrere Selektor-Strategien in fester
Reihenfolge:

**Inputs** (`_fill_input`):
1. `get_by_label(text, exact=True)`
2. `get_by_label(text)` (fuzzy)
3. `get_by_placeholder(text)`
4. `input[aria-label*=...]`

**Klicks** (`_click_text`):
1. `label:has-text("…")`  ← Wizard-Karten haben meist `<label>`-Wrapper
2. `[role="radio"]:has-text("…")`
3. `button:has-text("…")`
4. `get_by_role("radio", name=…)`
5. `get_by_role("button", name=…)`

Wichtig: Label-First-Reihenfolge verhindert, dass der Footer-Button „Ja"
(„Sind Sie zufrieden?") versehentlich getroffen wird, wenn das Wizard
ebenfalls „Ja" als Option hat (Step 7 Sanierung).

**Sanierungs-Klick** (`_click_sanierung_radio`): explizit mit
`:not(:has-text("zufrieden"))` als Schutz vor dem Footer-Button.

### 2. Adress-Autocomplete

Bei Step 2 muss man nach Eingabe der Straße einen Eintrag aus dem
Dropdown anklicken (Enter reicht nicht). Format: `"Prosperstraße, Essen"`
(Straße + Komma + Ort). Adapter probiert exakten Match zuerst, dann
Fallback auf den ersten Vorschlag mit der Straße.

### 3. Step-spezifische Eigenheiten

| Step | Element | Eingabe / Klick |
|---|---|---|
| 1 | Immobilienart | „Eigentumswohnung" (Auto-Advance) |
| 2 | Adresse | PLZ → Ort auto, Straße + Dropdown-Klick, Hausnr |
| 3 | Beweggrund | „Kauf (Kapitalanlage)" (Auto-Advance) |
| 4 | Kaufpreis + Miete | **beide leer lassen** — kein Einfluss auf Wert |
| 5 | Wohnfläche + Zimmer | `avg_wohnflaeche_qm`, `avg_zimmer` |
| 6 | Baujahr | `baujahr` |
| 7 | Sanierung | Ja wenn `sanierungsjahr_letztes ≠ None`, sonst Nein; inline-Jahr |
| 8 | Ausstattung | „Einfach" / „Gehoben" / „Luxus" (Auto-Advance, Mapping aus Datensatz) |
| 9 | Weitere Ausstattung | Parkplatz wenn `hat_garage OR hat_aussenstellplatz`; Submit |

### 4. Keine Trend-Auswertung im Adapter

Die Wertentwicklungs-Linie (Wertentwicklung-Tab) wird vom Adapter **nicht**
gelesen. Hintergründe:
- Der Zeitraum-Dropdown ist ein Material-UI-Custom-Element ohne stabilen
  Selektor — automatisches Umschalten auf „2 Jahre" greift nicht zuverlässig.
- SVG-Path-Heuristiken (Y-Bewegung der letzten 20 % der Datenpunkte) liefern
  unscharfe Ergebnisse je nach Highcharts-Default-Zeitraum.

Trend-Information liefern statt dessen die anderen Portale (CHECK24: 3J/1J/Prognose
mit konkreten %-Werten; Homeday: 12M-Trend Stadt + Wohnblock). Modul 0 nutzt
diese, Interhyp bleibt reiner Marktwert-Lieferant.

### 5. Ausstattung-Mapping

Der `GeneralisierterDatensatz.ausstattung` kann `einfach | normal | gehoben |
luxus` sein. Mapping zu Interhyp-Karten:

| Datensatz | Interhyp |
|---|---|
| `einfach` | Einfach |
| `normal` | **Einfach** (häufigster MFH-Default) |
| `gehoben` | Gehoben |
| `luxus` | Luxus |

Begründung: „normal" im Aufteiler-Standardflow heißt „durchschnittliche
MFH-Wohnung" — bei Interhyp-Klassen ist das „Einfach" (Kunststoffböden,
Einfach-Fenster) am nächsten.

### 6. Schema-Erweiterung: `sanierungsjahr_letztes`

`core/datensatz.py` wurde um ein optionales Feld erweitert:

```python
sanierungsjahr_letztes: Optional[int] = None
```

Logik: Wenn nach Baujahr ein größeres Gewerk (Dach, Heizung, Fassade, Fenster)
erneuert wurde → Jahr des **jüngsten** Gewerks setzen. Sonst `None`.

Beispiel Prosperstr. 59: Baujahr 1965, Dach 2020 → `sanierungsjahr_letztes=2020`.

Andere Adapter (CHECK24, Homeday) ignorieren das Feld.

## Output-Schema

Marktwert-Felder sind im **Standard-Top-Level** (wie bei CHECK24), portal-
spezifische Extras im `extra`-Slot. Realisiert über den `parse_marktwert`-
Hook in PortalBase, den Interhyp überschreibt.

```json
{
  "status": "ok",
  "portal": "interhyp",
  "marktwert_eur_min": 140000,
  "marktwert_eur_mittel": 162000,
  "marktwert_eur_max": 198000,
  "trends": {"jahre_3": null, "jahr_1": null, "prognose": null},
  "trend_label": "Marktwert 140.000 – 198.000 € (Mittel 162.000 €) Trend …",
  "extra": {
    "eur_per_qm": 2025,
    "eur_per_qm_einfach": 2025,
    "eur_per_qm_gehoben": 2150,
    "eur_per_qm_luxus": 2388,
    "marktwert_einfach_eur": 162000,
    "marktwert_gehoben_eur": 172000,
    "marktwert_luxus_eur": 191000,
    "ausstattung_klasse_gewaehlt": "einfach"
  }
}
```

**Wichtig**: `marktwert_eur_mittel` = Interhyp-eigener **Schätzwert** (162.000),
NICHT `eur_per_qm × wohnflaeche` (das wäre 162.000 ebenfalls, aber bei anderer
Ausstattungs-Klasse oder anderen Inputs könnten beide Pfade abweichen — der
Schätzwert ist Interhyp's offizielle Antwort).


## CLI-Aufruf

```powershell
.\.venv\Scripts\python.exe m00_portal_pricer.py `
  --portal interhyp `
  --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen `
  --baujahr 1965 --zustand gut --ausstattung normal `
  --anzahl-we 4 --gesamtwohnflaeche-qm 320 --gesamtzimmer 12 `
  --headless --verbose
```

Hinweis: Standard-CLI hat noch kein `--sanierungsjahr-letztes`-Arg. Bei Bedarf
direkt im Code setzen (oder CLI in einem späteren Step erweitern). Default
ohne Sanierungs-Info: Wizard wählt „Nein".

## Bekannte Stolpersteine

| Issue | Mitigation |
|---|---|
| Footer „Sind Sie zufrieden? Ja/Nein" kollidiert mit Sanierungs-Ja/Nein | `:not(:has-text("zufrieden"))`-Filter in `_click_sanierung_radio` |
| Cookie-Banner kommt mal/nicht (Session-State-abhängig) | `core/cookies.py` mit max_wait_s=12 toleriert das |
| PLZ → Ort auto-Befüllung braucht ~1.5s | `page.wait_for_timeout(1_500)` nach PLZ-Fill |
| Straßen-Autocomplete erfordert Klick, nicht Enter | `_click_strasse_dropdown_item` mit `li:has-text("…")` |
| „Größe des Parkplatzes" wird im Probe-Lauf nicht gefunden (anderes Label?) | Optional — wenn Feld fehlt, geht der Wizard trotzdem weiter |
| Wertentwicklung-Tab + Zeitraum-Dropdown sind Custom-Komponenten | Mehrere Selektor-Strategien; bei Fail → Trend = None |
| Material-UI Floating-Labels (`<label>`, nicht `placeholder`) | `get_by_label` vor `get_by_placeholder` priorisieren |

## Live-Verifikation

**Erwartung (Prosperstraße 59, 45357 Essen, OHNE Sanierungs-Info,
Ausstattung normal → Einfach):** (Stand End-to-End-Lauf 2026-05-15)
- `extra.marktwert_eur_min/mittel/max` = 140.000 / 162.000 / 198.000 €
- `extra.eur_per_qm_einfach` = 2.025 €/m²
- `extra.marktwert_einfach/gehoben/luxus_eur` = 162k / 172k / 191k

**Erwartung (gleiche Adresse MIT Sanierungsjahr 2020, im Sparring-Lauf
gesehen):**
- `extra.marktwert_eur_min/mittel/max` = 157.000 / 183.000 / 207.000 €
- `extra.eur_per_qm_einfach` = 2.288 €/m²

## Tests

```bash
pytest tests/test_portals_interhyp_*.py -v
```

**Tests:**
- Parser-Logik (`test_portals_interhyp_parsers.py`)
  - Marktwert-Min/Mittel/Max (5 Tests, inkl. Live-Layout + partial-Match)
  - EUR/m² je Ausstattungsklasse (3 Tests, inkl. Live-Layout)
  - Marktwert je Ausstattungsklasse (3 Tests, inkl. Live-Layout)
- 5 Smoke (`test_portals_interhyp_importable.py`)
  - Importierbarkeit + PortalBase-Subklasse
  - Selectors-Konstanten vollständig
  - PORTAL_REGISTRY enthält interhyp
  - `extract_extra` liefert erwartete Keys aus Sample-Body (ohne Trend-Felder)
  - GeneralisierterDatensatz-Feld `sanierungsjahr_letztes` existiert
