# CHECK24 PriceHugger Scraper

Standalone-Tool, das das CHECK24-Immobilienbewertungsformular automatisiert ausfüllt und einen Marktwert in € zurückgibt.

URL: <https://baufinanzierung.check24.de/baufinanzierung/immobilienbewertung>

## Setup (einmalig)

```powershell
cd C:\meine-projekte\Immobilien\Aufteiler\tools\check24
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Lauf

Aus `tools/check24/` mit aktivem venv:

```powershell
python ..\m00_check24_pricer.py `
  --adresse "Prosperstr. 59, 45356 Essen" `
  --objektart wohnung `
  --wohnflaeche-qm 75 `
  --zimmer 3 `
  --baujahr 1977 `
  --zustand gut
```

Output: JSON auf stdout, Screenshot der Ergebnisseite unter `runs/`.

Beim ersten Lauf **headed** (default) — Browser-Fenster geht auf, du siehst zu. Mit `--headless` umschalten, sobald die Selektoren in [dom_selectors.py](dom_selectors.py) bestätigt sind.

## Bei DOM-Änderungen

CHECK24 ändert das Formular gelegentlich. Wenn ein Step fehlschlägt:

1. Headed-Lauf starten, Browser bleibt am Fehlerpunkt stehen (Screenshot in `runs/`)
2. DevTools öffnen, korrekten Selektor finden
3. In [dom_selectors.py](dom_selectors.py) patchen
4. Neuer Versuch

## Tests

```powershell
pytest test_pricer.py
```

Smoke-Test, läuft **nicht in CI** — macht echte Requests gegen CHECK24.
