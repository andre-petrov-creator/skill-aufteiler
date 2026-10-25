# Portal: Immometrica

## Zweck

Adapter fuer **Immometrica.com**, ein Paid-B2B-Portal fuer
Immobilien-Investoren. Liefert objektspezifische Marktstatistiken
(Anzahl Angebote, Median Preis pro m², Median Onlinezeit, Rendite)
**pro PLZ und Stadt** fuer Kauf + Miete in der Asset-Klasse
ETW und Mehrfamilienhaus.

Step 14 im Implementierungsplan — ersetzt das urspruenglich geplante
ImmoScout24 als 4. Portal.

## Files

- `portals/immometrica/__init__.py`
- `portals/immometrica/parsers.py` — DOM-Body → Stat-Block-Parser
- `portals/immometrica/portal.py` — Adapter inkl. nodriver-Steuerung
- `inspectors/login_immometrica_autonomous.py` — Auto-Login + Cookie-Export
- `inspectors/training_immometrica.py` — Browser offen halten + Network-Sniff
- `inspectors/auto_statistics_immometrica.py` — Vollautonome 6-Filter-Sniff (Dev)
- `inspectors/sniff_immometrica_search.py` — Adress-Such-Probing (Dev)
- `inspectors/debug_immometrica_dom.py` — DOM-Inspector (Dev)
- `inspectors/probe_location_api.py` — Location-API-Probe (Dev)
- `inspectors/test_immometrica_adapter.py` — Live-Smoke-Test
- `tests/test_portals_immometrica_parsers.py` — 15 Unit-Tests (alle gruen)
- `learned_selectors/immometrica_nodriver_userdata/` — Browser-User-Daten
  (gitignored)
- `learned_selectors/immometrica_cookies.json` — Cookie-Snapshot (gitignored)
- `.env` — Login-Credentials `IMMOMETRICA_USERNAME` / `IMMOMETRICA_PASSWORD`

## Architektur — anders als andere Portale

Immometrica verwendet **reCAPTCHA v2** vor dem Login, das Standard-Playwright
sofort blockt ("keine Verbindung zum reCAPTCHA-Dienst"). Selbst System-Chrome
mit `channel="chrome"` + `--disable-blink-features=AutomationControlled`
reicht nicht.

Loesung: **[nodriver](https://github.com/ultrafunkamsterdam/nodriver) statt
Playwright**. Modernster Anti-Detection-Chrome-Treiber (Successor zu
undetected-chromedriver), steuert Chrome direkt via CDP mit allen
bekannten Bot-Markern gepatcht.

Konsequenz:
- Adapter erbt **nicht** von `PortalBase`. PortalBase ist Playwright-spezifisch.
- Adapter hat eigene `run_immometrica(plz, stadt)` Sync-API.
- CLI `m00_portal_pricer.py` hat einen Special-Case fuer `--portal immometrica`.

## Datenfluss (Phase 2)

```
m00_portal_pricer.py --portal immometrica --datensatz <json>
   │
   ▼
portals.immometrica.portal.run_immometrica(plz, stadt, baujahr, year_half, headless)
   │
   ├──► nodriver: launch_persistent_context(user_data_dir=...)
   │       └── Persistente Cookies → kein Re-Login noetig
   │           Falls Session abgelaufen: _do_login() mit .env-Credentials
   │
   ├──► Initialisierung (1x pro Lauf):
   │       1. tab.get("https://www.immometrica.com/de/home")  ← Dashboard
   │       2. Sleep 8s (App-Hydration)
   │       3. Login-Check via _login_state() — URL + App-Navigation
   │          (Redirect auf /de/accounts/login/ = Session weg → _do_login)
   │       4. _click_marktstatistik_sidebar()  ← Sidebar-Klick auf "Marktstatistik"
   │       5. Sleep 8s
   │       6. _wait_for_marktstatistik_ready() — ohne Formular harter Abbruch
   │          mit error_code `session_lost` bzw. `statistics_form_not_ready`
   │       7. _select_period("latest")  ← Default-Halbjahr, nur klicken wenn nicht aktiv
   │
   ├──► 6 Configs (gruppiert: PLZ-Block, dann Stadt-Block, KEIN tab.get zwischen):
   │       #  Geo    Radio          MFH
   │       1  PLZ    ETW            off    } Geo-Set 1× am Anfang des PLZ-Blocks
   │       2  PLZ    Mietwohnung    off    }
   │       3  PLZ    Hauskauf       on     }
   │       4  Stadt  ETW            off    } Geo-Wechsel auf Stadt 1×
   │       5  Stadt  Mietwohnung    off    }
   │       6  Stadt  Hauskauf       on     }
   │
   │       Pro Config:
   │         1. Falls Geo-Wechsel: _enter_geo(geo, exp)
   │              → _clear_geo_tags + location-toggle + tippen char-by-char
   │              + _press_enter (CDP-Keystroke, NICHT send_keys('Enter'))
   │              + 3s Tag-Erscheinen-Wait
   │         2. _click_bauliches_tab()
   │         3. _set_baujahr_range(baujahr=1900, baujahr_bis=max(1980, BJ+5))
   │         4. MFH-Checkbox: an bei Hauskauf, aus sonst
   │         5. _select_radio + verify
   │         6. _click_create_stat()
   │         7. _wait_for_stat_loaded()
   │         8. body = innerText → parsers.parse_stat_block(body)  ← 9 Tabellen
   │
   └──► Final: dict mit RunResult-Schema + extra-Slot (6 Configs × 9 Tabellen)
```

## Architektur-Regeln

- **KEIN `tab.get` zwischen Configs.** IntercoolerJS-Server-State bleibt sticky.
- **Geo IMMER vor Period.** Period-Klick triggert Partial-Reload, der React-Select-Input bricht.
- **Geo nur bei Geo-Wechsel neu setzen** (2× pro Lauf: PLZ + Stadt).
- **Enter via CDP `dispatch_key_event`** (nicht `send_keys("Enter")` — das macht char-Events).
- **MFH-Toggle pro Config explizit** setzen, nicht auf sticky State verlassen.
- **`_ensure_logged_in` Sleep 8s** (nicht 3s — App-Hydration langsam).
- **`_click_marktstatistik_sidebar` statt direkter URL** — `tab.get("/de/statistics")` bricht React-Select.

## Output-Schema (Phase 2)

```json
{
  "status": "ok|partial|error",
  "portal": "immometrica",
  "marktwert_eur_mittel": null,
  "marktwert_eur_min": null,
  "marktwert_eur_max": null,
  "trends": {"jahre_3": null, "jahr_1": null, "prognose": null},
  "trend_ampel": null,
  "trend_label": null,
  "url": "https://www.immometrica.com/de/statistics",
  "timestamp": "<iso>",
  "extra": {
    "year_half": "H1/2026",
    "plz_input": "45357",
    "stadt_input": "Essen",
    "baujahr_input": 1965,
    "baujahr_bis_filter": 1980,
    "plz_etw":         {"status": "ok", "geo_state": "...", "tables": {...9 tables...}},
    "plz_mietwohnung": {"status": "ok", ...},
    "plz_mfh":         {"status": "ok", ...},
    "stadt_etw":       {"status": "ok", ...},
    "stadt_mietwohnung":{"status": "ok", ...},
    "stadt_mfh":       {"status": "ok", ...}
  }
}
```

Jeder Config-Block enthaelt `tables` mit allen 9 Tabellen, die Immometrica
auf der Marktstatistik-Page rendert. Exakte Tabellen-Liste wird ueber
Live-DOM-Diagnose ermittelt (siehe Memory [[immometrica-9-tabellen]]). Bisherige
2 Bloecke `uebersicht` + `zusatzinfo` sind eine Teilmenge.

**Wichtig:** `marktwert_eur_*` ist immer `null`, weil Immometrica keine
objektspezifische Marktwert-Schaetzung in dem Sinne liefert (das macht
der Sprengnetter-AVM-Wertbericht hinter einer separaten Bezahlschranke).
Modul 0 nutzt die Statistiken zur Quervalidierung des CHECK24/Homeday-
Marktwerts und fuer Markt-Score (Anbieter-Dichte, Onlinezeit-Indikator,
Renditen).

## Phase-2-Architektur (autonom)

**Status: alle Filter autonom** (User-Workaround entfernt).

| Filter | Loesung |
|---|---|
| Halbjahr | `_select_period("latest")` — neuester Button automatisch |
| Object-Typ-Radio (ETW/Mietwohnung/Hauskauf) | `_select_radio` + Verifikation + Retry |
| Bauliches: MFH-Checkbox an/aus | `_click_mfh_checkbox` + Verifikation + Retry |
| **Baujahr-Range** | `_set_baujahr_range(1900, max(1980, BJ+5))` |
| Ort via React-Select | `_enter_geo` mit **Enter via CDP** statt Native-Click — funktioniert nur wenn Geo VOR Period gesetzt wird, kein `tab.get` zwischen Configs |

**Wesentlich gegenueber Phase 1:**
- Direkte URL-Navigation `/de/statistics` ersetzt durch `_click_marktstatistik_sidebar` (App-eigene Initialisierung).
- `tab.get` zwischen Configs entfernt — sticky IntercoolerJS-State nutzen.
- Geo-Eingabe via React-Select-Tippen + CDP-Enter-Keystroke statt `send_keys("Enter")`-String.
- 6 Configs statt 4 (ETW + Mietwohnung + Hauskauf × PLZ + Stadt).
- Baujahr-Filter pro Config aktiv.

### Login gegen das v2-Formular (Stand 2026-09-10)

Immometrica hat das Login-Formular ausgetauscht. Massgeblich ist jetzt
`https://www.immometrica.com/de/accounts/login/?next=/de/home` mit:

| Element | Selektor |
|---|---|
| Formular | `form.auth-form[data-testid="v2-login-form"]` |
| E-Mail | `input[type="email"]` / `#id_login` (`name="login"`) |
| Passwort | `input[type="password"]` / `#id_password` |
| Angemeldet bleiben | `#id_remember` |
| Submit | `[data-testid="v2-login-submit"]` (Fallback `form.auth-form button[type="submit"]`) |

**Text-Suche ist auf diesem Formular verboten.** nodrivers `tab.find` matcht
auch Attributwerte:

- `find("Login")` → `<input id="id_login">`, also das **E-Mail-Feld**
- `find("Anmelden")` → `<h1 class="auth-title">Anmelden</h1>`, die Ueberschrift

Beide Klicks submitten nichts. Genau das war die Ursache des Totalausfalls vom
2026-09-10 (siehe Changelog). `_do_login` arbeitet deshalb ausschliesslich mit
Selektoren und verifiziert den Erfolg per `_wait_for_login_confirmed`
(Polling auf URL ohne `/accounts/login` **und** `Logout`/`Profil` im Body),
statt wie vorher blind `True` zu liefern.

`#id_remember` wird gesetzt, damit die Session im persistenten User-Data-Dir
zwischen zwei Aufteiler-Laeufen ueberdauert.

Das Formular traegt einen Proof-of-Work-Bot-Check
(`data-pow-captcha="1"`, `data-pow-url="/de/accounts/bot-check/challenge"`,
Hidden-Feld `#id_pow_payload`). Der wird von der Seiten-JS selbst erledigt —
im Live-Test 2026-09-10 lief der Login durch, ohne dass der Adapter das Feld
anfassen musste. Ein sichtbares reCAPTCHA gibt es auf dieser Route nicht mehr.

Fallback bei hartnaeckigem Login-Fehler: manuelles
`inspectors/login_immometrica_autonomous.py` einmal laufen lassen, dann ist der
State wieder frisch.

### ToS-Risiko

Immometrica's AGB fuer Investor/Pro-Abos verbieten mit hoher
Wahrscheinlichkeit automatisierte Abfragen. Risiko: Account-Sperre.
Mitigation:
- Max 1× pro Aufteiler-Lauf
- Keine Bulk-Abfragen
- Keine festen Zeitfenster

Diese sind im Adapter aktuell NICHT enforced — User entscheidet pro Lauf.

## Schnittstellen

### Python-API

```python
from portals.immometrica.portal import run_immometrica

result = run_immometrica(
    plz="45357",
    stadt="Essen",
    year_half="H1/2026",
    headless=True,
)
# result: dict mit dem oben dokumentierten Schema
```

### CLI

```bash
.venv/Scripts/python.exe m00_portal_pricer.py \
  --portal immometrica \
  --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen \
  --baujahr 1965 --zustand gut --ausstattung normal \
  --anzahl-we 4 --gesamtwohnflaeche-qm 320 --gesamtzimmer 12 \
  --headless
```

## Smoke-Test

Voraussetzung: `learned_selectors/immometrica_nodriver_userdata/` existiert
(einmaliger Login bereits durchgefuehrt) UND der User hat einmal manuell
die gewuenschten Filter in der Marktstatistik-Page gesetzt.

```bash
.venv/Scripts/python.exe inspectors/test_immometrica_adapter.py
```

Erwartet: Status `ok`, alle 4 extra-Slots gefuellt mit `uebersicht`-Werten.

## Config-Status — was der Adapter pro Slot melden kann

| Status | Bedeutung | Werte im Output |
|---|---|---|
| `ok` | Ort-Tag + Heading passen zur Config, Stat-Seite geladen | vollstaendig |
| `geo_mismatch` | Ort-Tag der Ergebnis-Seite passt nicht zur Config | `uebersicht`/`zusatzinfo`/`charts` bewusst `null` |
| `geo_not_set` | Ort liess sich gar nicht setzen, Config nicht submittet | `null` |
| `stale_heading` | Stat-Seite haengt auf der vorherigen Config (v3.3) | `null` |
| `partial` | geladen, aber kein `uebersicht`-Block parsebar | teilweise |
| `error` | Stat-Seite nicht geladen | `null` |

Diagnose-Felder pro Slot: `geo_check.{expected,actual,match}` und
`heading_check.{expected,actual,match}`.

Lauf-Level `error_code`: `all_configs_failed`, `partial_configs`,
`login_failed`, `session_lost`, `statistics_form_not_ready`, `exception`.

**Konsumenten (Modul 1, Orchestrator) duerfen nur `status == "ok"` auswerten.**

## Bekannte Limitierungen

- **Nur aktuelles Halbjahr** (kein Preisverlauf, User-Klaerung). Referenzwerte
  aus alten Laeufen sind deshalb nicht 1:1 vergleichbar — bei PLZ-Ebene
  schwankt der Median mit kleiner Inseratszahl deutlich.
- **Blind-Sleeps sind hier gefaehrlich.** Das React-Select-Ort-Menue schliesst
  sich wieder; ein fixer Sleep zwischen Tippen und Enter liess den Keystroke
  ins Leere laufen und den Ort ungesetzt (Ausfall 2026-09-10). Deshalb
  `_wait_for_geo_suggestions` — Enter erst, wenn Optionen nachweislich offen sind.

## Changelog

### 2026-09-10 — Login-Fix + Geo-Gate

Symptom: `all_configs_failed`, alle sechs Configs `submit_button_not_found`.

Zwei unabhaengige Ursachen:

1. **Login stumm gescheitert.** Neues v2-Formular, Text-Suche traf E-Mail-Feld
   und `<h1>` statt Submit; `_do_login` meldete trotzdem Erfolg. Der Adapter
   arbeitete auf der Login-Seite weiter → kein Submit-Button.
   Fix: Selektoren + echte Verifikation + `#id_remember`.
2. **Ort-Filter wurde nicht gesetzt** (fiel erst nach Fix 1 auf). Enter traf ein
   inzwischen geschlossenes Vorschlags-Menue. Immometrica lieferte bundesweite
   Zahlen, die der Adapter als PLZ-/Stadt-Werte mit `status: ok` meldete
   (41284 Angebote / 3341 EUR/m2 statt 12 / 2151 fuer 45355 Essen).
   Fix: `_wait_for_geo_suggestions` + `_geo_state_matches`-Gegenprobe auf der
   Ergebnis-Seite + Skip statt Submit bei ungesetztem Ort.

Verifikation Essen-Frintrop (45355 / Essen, Baujahr 1969, Filter 1900-1980):
Stadt-ETW 2342 EUR/m2 gegen Referenz 2319 EUR/m2 vom 2026-06-26 (+1,0 %),
Rendite 4,8 % identisch. Tests: `tests/test_portals_immometrica_login.py`,
`tests/test_portals_immometrica_geo.py`.

## Memory-Bezuege

- [[immobilien-portale-strassen-kurzform]] — Immometrica nutzt keine
  Strassen-Eingabe (nur PLZ + Stadt), Strassen-Kurzform irrelevant.
- [[portal-bewertung-blueprint-workflow]] — Step 14 jetzt mit
  Filter-Limit-Caveat.
- [[portal-bewertung-step-14-immometrica]] — komprimierter Stand.
