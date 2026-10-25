# Neues Portal hinzufügen

Schritt-für-Schritt-Anleitung für das Hinzufügen eines neuen
Bewertungs-Portals (Homeday, Interhyp, IS24, ...).

## Vorbereitung

1. **Screenshots vom User einholen** (3 Stück):
   - Startseite mit Cookie-Banner — markiert: welcher Button anklicken
   - Eingabeformular — markiert: welche Felder in welcher Reihenfolge
   - Ergebnisseite — markiert: wo der Marktwert steht
2. **User-Hinweise** abklären: Captcha? E-Mail-Zwang? Anti-Bot beobachtet?

## Schritt 1: DOM dumpen

```bash
cd c:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung
.\.venv\Scripts\python.exe inspectors\inspect_dom.py `
  https://example.de/bewertung `
  --out homeday_dump.json `
  --headed
```

→ liefert `homeday_dump.json` (alle Inputs/Selects/Radios mit Labels)
und `homeday_dump.png` (Screenshot der Seite).

## Schritt 2: `portals/<name>/selectors.py` anlegen

Pflicht-Konstanten:

```python
START_URL = "https://example.de/bewertung"

COOKIE_ACCEPT_CANDIDATES = [
    'button:has-text("Alle akzeptieren")',
    'button:has-text("OK")',
]
COOKIE_WRAPPER = "#cookie-banner"  # für Verschwinde-Check, optional

SUBMIT_BUTTON = "#submit-bewertung"
RESULT_FRAME_MARKER = "Marktwertermittlung"  # eindeutiger Text im Result

# Input-Indices oder direkte Selektoren — je nach Portal-Aufbau
INPUT_PLZ = 0
INPUT_STRASSE = 1
# ...

# Option-Maps zur Übersetzung Datensatz-Wert → Portal-Label
ZUSTAND_OPTION = {
    "gut": "Gut erhalten",
    # ...
}
```

## Schritt 3: `portals/<name>/portal.py` anlegen

```python
from typing import Any

from core.datensatz import GeneralisierterDatensatz
from core.inputs import input_typed, input_street_with_autocomplete
from core.modals import dismiss_modal_by_text
from core.portal_base import PortalBase, RunConfig
from core.selects import select_by_index

from . import selectors as sel


class HomedayPortal(PortalBase):
    NAME = "homeday"
    START_URL = sel.START_URL
    COOKIE_ACCEPT_CANDIDATES = sel.COOKIE_ACCEPT_CANDIDATES
    COOKIE_WRAPPER = sel.COOKIE_WRAPPER
    SUBMIT_SELECTOR = sel.SUBMIT_BUTTON
    RESULT_FRAME_MARKER = sel.RESULT_FRAME_MARKER

    def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
        input_typed(page, sel.FORM_INPUTS, d.plz, index=sel.INPUT_PLZ)
        input_street_with_autocomplete(
            page, sel.FORM_INPUTS, d.strasse, index=sel.INPUT_STRASSE
        )
        # ... weitere Felder

    def dismiss_post_submit_modals(self, page: Any) -> None:
        dismiss_modal_by_text(page, ["später erinnern", "OK", "Schließen"])
```

## Schritt 4: CLI-Registry erweitern

In [m00_portal_pricer.py](../m00_portal_pricer.py):

```python
from portals.homeday.portal import HomedayPortal

PORTAL_REGISTRY: dict[str, type[PortalBase]] = {
    "check24": Check24Portal,
    "homeday": HomedayPortal,
}
```

## Schritt 5: Smoke-Test

`tests/test_portals_<name>_importable.py`:

```python
def test_homeday_portal_imports_and_subclasses_portal_base() -> None:
    from core.portal_base import PortalBase
    from portals.homeday.portal import HomedayPortal
    assert issubclass(HomedayPortal, PortalBase)
    assert HomedayPortal().NAME == "homeday"
```

## Schritt 6: Live-Test

```bash
.\.venv\Scripts\python.exe m00_portal_pricer.py `
  --portal homeday `
  --strasse "Prosperstraße" --hausnr 59 `
  --plz 45357 --ort Essen --baujahr 1965 `
  --zustand gut --ausstattung normal `
  --anzahl-we 4 --gesamtwohnflaeche-qm 320 --gesamtzimmer 12 `
  --headed --verbose
```

Erwartung: plausibler Marktwert im Bereich ±20% vom CHECK24-Wert.

## Schritt 7: Doku

`docs/portal-<name>.md` analog zu [portal-check24.md](./portal-check24.md):
- Bekannte Stolpersteine (Cookie-Banner-Text, Captcha-Quirks)
- Form-Reihenfolge
- Live-Verifikations-Aufruf

## Schritt 8: Commit

```bash
git add portals/homeday/ tests/test_portals_homeday_importable.py \
        docs/portal-homeday.md m00_portal_pricer.py
git commit -m "feat(portal-bewertung): homeday portal adapter"
git push origin main
```
