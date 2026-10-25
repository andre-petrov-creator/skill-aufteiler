# `inspectors/` — Dev-Tools für neue Portale

## Zweck

Beim Hinzufügen eines neuen Bewertungs-Portals (Homeday, Interhyp, IS24, ...)
muss man rausfinden, welche `<input>`-, `<select>`- und Radio-Felder das
Portal hat, in welcher Reihenfolge, mit welchen Labels. Diese Tools machen
das automatisch: öffnen die Seite, klicken Best-Effort Cookies weg, dumpen
alle relevanten DOM-Elemente in JSON + machen einen Screenshot.

## Tools

### `inspect_dom.py` — generischer DOM-Inspector

```bash
# Headless (Default)
python inspectors/inspect_dom.py https://example.de/bewertung \\
  --out homeday_dump.json

# Mit sichtbarem Browser (für manuelle Verifikation)
python inspectors/inspect_dom.py https://example.de/bewertung \\
  --out homeday_dump.json \\
  --headed
```

**Output:** `homeday_dump.json` mit Struktur:

```json
{
  "url": "https://example.de/bewertung",
  "cookie_dismissed": true,
  "inputs":  [{ "tag": "INPUT", "type": "text", "label": "Postleitzahl", "qaRef": "...", "placeholder": "PLZ", ... }],
  "selects": [{ "tag": "SELECT", "label": "Immobilientyp", "options": ["Eigentumswohnung", "Einfamilienhaus", ...], ... }],
  "radios":  [{ "tag": "RADIO", "qaRef": "kaufabsicht", "value": "kauf", "label": "Ich möchte kaufen" }],
  "buttons": [{ "tag": "BUTTON", "text": "Bewertung starten", "type": "submit", ... }]
}
```

Plus Screenshot unter `homeday_dump.png` (gleicher Pfad, anderes Suffix).

### Cookie-Banner-Best-Effort-Liste

Der Inspector probiert in dieser Reihenfolge:

- `button:has-text("Akzeptieren")`
- `button:has-text("Alle akzeptieren")`
- `button:has-text("Zustimmen")`
- `button:has-text("OK")`
- `button:has-text("geht klar")` / `button:has-text("Geht klar")`
- `button:has-text("Verstanden")`
- `button:has-text("Schließen")`
- `#cookie-accept`
- `[id*='cookie'][id*='accept']`

Wenn keiner passt → `cookie_dismissed: false` im Dump → manuell schauen,
welchen Selektor das Portal nutzt, dann in den Portal-Adapter aufnehmen.

## Workflow für neue Portale

1. **DOM dumpen:** `python inspectors/inspect_dom.py <portal-url> --out <name>_dump.json`
2. **JSON ansehen:** Inputs/Selects/Radios identifizieren, ihre Labels +
   Selektoren extrahieren
3. **`portals/<name>/selectors.py`** anlegen mit den Konstanten
   (START_URL, COOKIE_*, SUBMIT_*, Input-Indices, Option-Maps)
4. **`portals/<name>/portal.py`** anlegen — `class <Name>Portal(PortalBase)`
   mit `fill_form` (siehe [docs/portal-base.md](../docs/portal-base.md)
   für das Mini-Tutorial)
5. **CLI-Registry erweitern:** `PORTAL_REGISTRY` in
   [m00_portal_pricer.py](../m00_portal_pricer.py) ergänzen
6. **Live-Test:** `python m00_portal_pricer.py --portal <name> ... --headed`

## Bekannte Limitierungen

- **Cookie-Banner mit shadowDOM** werden ggf. nicht erkannt — manuell
  schauen.
- **Lazy-loaded Formulare** (JS-Hydration nach DOM-Load): `--wait-after-load-ms`
  hochsetzen.
- **Captcha-/Bot-Detection** macht der Inspector nicht — wenn das Portal
  bei `wait_until="domcontentloaded"` schon redirected, sieht man das
  am Screenshot.
