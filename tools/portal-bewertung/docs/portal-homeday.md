# `portals/homeday/` — Homeday-Preisatlas-Adapter

## Zweck

Homeday liefert für eine Adresse **Quadratmeterpreis (€/m²)** + Wohnlage-Bewertung
+ 12-Monats-Preistrend für Stadt & Wohnblock. **Keine** absoluten
Marktwert-Spannen wie CHECK24 — der Output liegt deshalb im
`RunResult.extra`-Slot statt im klassischen `marktwert_eur_*`-Schema.

## Files

- [portals/homeday/selectors.py](../portals/homeday/selectors.py) — Cookies, URL-Bauer, Selektoren
- [portals/homeday/parsers.py](../portals/homeday/parsers.py) — Body-Text-Regex + Ampel-Logik
- [portals/homeday/portal.py](../portals/homeday/portal.py) — `HomedayPortal(PortalBase)` + `parse_homeday_extras`
- [tests/test_portals_homeday_parsers.py](../tests/test_portals_homeday_parsers.py) — 16 Parser-Tests
- [tests/test_portals_homeday_url.py](../tests/test_portals_homeday_url.py) — 6 URL-Builder-Tests
- [tests/test_portals_homeday_importable.py](../tests/test_portals_homeday_importable.py) — 4 Smoke-Tests

## Architektur-Eigenheiten

### 1. Deep-Link statt Formular

Homeday hat eine deeplinkbare Result-URL:

```
https://www.homeday.de/de/preisatlas/<stadt>/<strasse>+<hausnr>,+<plz>
  ?map_layer=standard&marketing_type=sell&property_type=apartment
```

`HomedayPortal.fill_form` navigiert direkt dorthin — keine Form-Befüllung,
kein Submit-Klick. `SUBMIT_SELECTOR = ""` → `core/runner.py` überspringt
den Submit-Step automatisch.

URL-Slug-Regeln:
- Straße: `Prosperstraße` → `prosperstrasse` (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`)
- Stadt: `Mülheim an der Ruhr` → `muelheim-an-der-ruhr`
- Hausnr leer → URL ohne Hausnummer (`prosperstrasse,+45357`) — Homeday akzeptiert das

### 2. Cookiebot-Banner (`<a>`-Tag, nicht `<button>`)

Cookie-Banner wird von **Cookiebot** gerendert (consentcdn.cookiebot.com).
Der Akzeptieren-Button ist ein `<a>`-Tag mit ID:

```
#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll
```

Standard-`button:has-text("Alle akzeptieren")` matched das NICHT — daher
ID-Selektor als primärer Kandidat.

### 3. Output-Schema-Erweiterung via `extra`

`marktwert_eur_*` und `trends` bleiben `None` — Homeday liefert kein
absolutes Marktwert-Schema. Stattdessen schreibt der Adapter ins
`RunResult.extra`:

```json
{
  "eur_per_qm": 1700,
  "wohnblock_wohnlage": "einfach",
  "wohnblock_farbe_hex": "#FFE873",
  "trend_12m_stadt_pct": 6.0,
  "trend_12m_stadt_ampel": "gruen",
  "trend_12m_stadt_ampel_label": "steigend (+6.0%)",
  "trend_12m_wohnblock_pct": null,
  "trend_12m_wohnblock_ampel": "grau",
  "trend_12m_wohnblock_ampel_label": "— (keine Daten)"
}
```

## Ampel-Logik (User-Vorgabe)

Trends werden auf den **12-Monats-Wert** angewendet (Homeday liefert
keinen 3-Jahres-%-Wert als Zahl — nur als Chart):

| Bedingung | Ampel | Label |
|---|---|---|
| `> +1 %` | grün | „steigend (+x.x%)" |
| `\|x\| ≤ 1 %` | gelb | „stagnierend (±x.x%)" |
| `< -1 %` | rot | „fallend (-x.x%)" |
| `None` (Homeday: „—") | grau | „— (keine Daten)" |

## Wohnlage-Farbskala (Homeday-Legende)

| Label | Hex | Visuell |
|---|---|---|
| einfach | `#FFE873` | hellgelb |
| mittel | `#F7A823` | orange |
| gut | `#F76923` | rot-orange |
| sehr gut | `#C8312B` | rot |
| herausragend | `#7B2D8E` | lila |

## CLI-Aufruf

```powershell
.\.venv\Scripts\python.exe m00_portal_pricer.py `
  --portal homeday `
  --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen `
  --baujahr 1965 --zustand gut --ausstattung normal `
  --anzahl-we 4 --gesamtwohnflaeche-qm 320 --gesamtzimmer 12 `
  --headless --verbose
```

Hausnummer optional — `--hausnr ""` oder weglassen funktioniert:

```powershell
.\.venv\Scripts\python.exe m00_portal_pricer.py `
  --portal homeday `
  --strasse "Prosperstraße" --plz 45357 --ort Essen ...
```

## Bekannte Stolpersteine

| Issue | Mitigation |
|---|---|
| Cookiebot-Button ist `<a>`, nicht `<button>` | Spezieller ID-Selektor `#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll` |
| 12M-Trend kann `—` sein (Wohnblock zu klein) | Parser liefert `None` → Ampel = „grau" |
| Wohnlage „Einfach" steht auf einer Map-Marker-Card, schwer per CSS-Selektor zu finden | Body-Text-Regex `Wohnlage\\n<Label>\\n` |
| URL braucht eigene Slug-Logik (ä → ae, etc.) | `_slugify_strasse` + `_slugify_stadt` in `selectors.py` |
| Marketing-Type / Property-Type per URL-Parameter | `HomedayPortal(marketing_type="rent", property_type="house")` im Konstruktor |
| Adress-Eingabe-Fallback (falls Deep-Link bricht) | `selectors.ADDRESS_INPUT` definiert, aber im Adapter aktuell ungenutzt |
| Cookiebot legt LocalStorage-Cookie nach Klick | Banner kommt auf der Result-URL nicht erneut |

## Live-Verifikation

**Erwartung (Prosperstraße 59, 45357 Essen):**
- `eur_per_qm` ≈ 1.700 €/m²
- `wohnblock_wohnlage` = `"einfach"`
- `wohnblock_farbe_hex` = `"#FFE873"`
- `trend_12m_stadt_pct` ≈ 6.0
- `trend_12m_wohnblock_pct` = `None` („—")

**Hinweis:** Live-Verifikation muss vom User ausgeführt werden — der
Sparring-Lauf (2026-05-15) hat das DOM ausgewertet, aber kein
End-to-End-CLI-Aufruf gegen die echte Site.

## Tests

```bash
pytest tests/test_portals_homeday_*.py -v
```

26 Tests: 16 Parser-Logik + 6 URL-Builder + 4 Smoke (Importierbarkeit +
Registry + Extra-Extraktion mit echtem Body-Sample).
