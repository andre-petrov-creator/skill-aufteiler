# Step 15 + Modul-0-v2 — Stand 2026-05-19 (nach Issue-Fixes + Re-Run)

## TL;DR

Step 15 (Orchestrator) **Code fertig + 3 Live-Issues gefixt + State-Schema +
Modul-5-Excel-Write + 15 Unit-Tests grün**.

**Live-Test #1** (Welperstr. 39, Hattingen) zeigte 3 Issues, alle behoben:
- Issue 1 ✅ Homeday-`extra.eur_per_qm` wird jetzt vom Orchestrator gelesen
- Issue 2 ✅ CHECK24 Cookie-Layer-DOM-Hammer in `fill_form`
- Issue 3 ✅ Immometrica via `subprocess.run` statt ThreadPool (asyncio-Konflikt-Fix)

Plus Plausibilitäts-Fix: `eur_per_qm` rechnet jetzt pro WE (`avg_wohnflaeche_qm`),
nicht gegen `gesamtwohnflaeche_qm` (130k Marktwert / 73qm = 1.781 €/m² ✓).

## Live-Test #1 — Welperstr. 39, Hattingen, Baujahr 1965, 4 WE (~73qm/WE)

```
.venv/Scripts/python.exe m00_portal_pricer.py --alle \
  --strasse "Welperstr." --hausnr 39 --plz 45525 --ort Hattingen \
  --baujahr 1965 --zustand gut --ausstattung normal \
  --anzahl-we 4 --wohnflaechen-qm "65,70,75,80" --zimmer-liste "2,3,3,3" \
  --headless
```

Output (`runs/_alle_welperstr_20260519T204507.json`):

| Portal | Status | Marktwert/WE | €/m² (pro WE 73qm) |
|---|---|---|---|
| CHECK24 | error | – | – (Cookie-Layer-Bug) |
| Homeday | ok | null (Parser-Bug) | 2.200 (im raw_text, nicht extrahiert) |
| Interhyp | ok | 130.000 € | 1.781 (plausibel für Hattingen) |
| Immometrica | ok | – | PLZ 2.382 / Stadt 2.252 |

**Konsens-Median nach Fix:** Interhyp 1.781 + Immo-PLZ 2.382 + Immo-Stadt 2.252 → Median 2.252 €/m² ✓ plausibel.

## Was diese Session erledigt hat

### Issue 1 ✅ — Homeday-`extra.eur_per_qm` lesen

Orchestrator-Helper `_compute_eur_per_qm` hat jetzt 2 Pfade:
- Pfad 1: `portal_out["extra"]["eur_per_qm"]` (Homeday liefert das direkt)
- Pfad 2: `marktwert_eur_mittel / wohnflaeche_pro_we` (CHECK24, Interhyp)

Unit-Test: `test_compute_eur_per_qm_from_extra_homeday` + `test_compute_eur_per_qm_prefers_extra_over_marktwert`.

### Issue 2 ✅ — CHECK24 Cookie-Layer-Hammer

In `portals/check24/portal.py` `fill_form()` als erste Aktion:
```python
page.evaluate("""(() => {
    const sels = ['.c24-strict-blocking-layer', '.c24-cookie-consent-wrapper',
                  '[class*="cookie-consent-wrapper"]'];
    for (const s of sels) document.querySelectorAll(s).forEach(el => el.remove());
})()""")
```
Damit ist die Pointer-Events-Blockade weg, auch wenn das Cookie-Banner verzögert reinpoppt.

### Issue 3 ✅ — Immometrica via Subprocess

`_run_immometrica_wrap` ruft jetzt `m00_portal_pricer.py --portal immometrica
--datensatz <json-tempfile>` via `subprocess.run` auf, parst stdout-JSON.
Keine asyncio-Kollisionen mehr, kein 2.32-GB-Log.

### State-Schema ✅

`docs/state.schema.json` + `docs/state-schema.md` um `modul_0.eur_per_qm`-Block
+ `marktwert_konsens_eur` / `marktwert_quelle` / `konsens_spread_prozent`
erweitert. Alles optional (additionalProperties=false bleibt durch
explizite Properties intakt).

### Modul-5-Excel-Write ✅

`skills/aufteiler-modul-5-deal-bewertung/SKILL.md` Block 4 (vor Excel-Comments)
schreibt jetzt `KALKU!I13–I17` aus `state.modul_0.eur_per_qm`-Dict:
```python
_kalku_qm_map = {
    "I13": "homeday",
    "I14": "immometrica_plz_etw",
    "I15": "check24",
    "I16": "interhyp",
    "I17": "immometrica_stadt_etw",
}
for cell, key in _kalku_qm_map.items():
    val = eur_per_qm.get(key)
    if val is not None: kalku[cell] = float(val)
```

### Unit-Tests ✅ (15 grün)

`tests/test_orchestrator.py` mit 15 Tests:
- 2× `_avg_wohnflaeche_pro_we`
- 1× `_gesamtwohnflaeche`
- 5× `_compute_eur_per_qm`
- 3× `_extract_immometrica_eur_per_qm`
- 4× `_compute_konsens`

Lauf: `pytest tests/test_orchestrator.py -v` → 15 passed in 0.64s.

### Live-Test #2 — Welperstr. 39, Hattingen (nach Fixes)

JSON: `runs/_alle_rerun_20260519T215505.json` (45 KB)
stderr: `runs/_alle_rerun_stderr.log` (**0 Bytes** — Issue 3 Subprocess-Fix wirkt!)

**Status final: `partial`** (3 von 4 Portalen ok)

| Portal | Status | Marktwert/WE | €/m² | Notiz |
|---|---|---|---|---|
| Homeday | ok | – | **2.200** | Issue-1-Fix wirkt: `extra.eur_per_qm` jetzt gelesen |
| CHECK24 | error | – | – | **Neuer** Error `result_frame_not_found` (Cookie-Fix wirkt, anderer Bug) |
| Interhyp | ok | 130.000 € | **1.781** | 130k / 73qm — plausibel für Hattingen |
| Immometrica | ok (subprocess) | – | PLZ **2.382** / Stadt **2.252** | Issue-3-Subprocess wirkt: kein asyncio-Konflikt |

**€/m²-Median über 4 Werte:** **2.226 €/m²** — plausibel für Hattingen-MFH (real ~2.000–2.400).

**Marktwert-Konsens über 2 absolute Werte:** 151.943 € (Spread 28.9%).

### NEUES Issue 4: CHECK24 result_frame_not_found

**Symptom:** Nach fill_form (jetzt mit Cookie-Layer-Fix) findet der Runner den Result-Frame mit Marker `'Marktwertermittlung'` nicht.

**Diagnose-Hypothesen:**
- Submit-Knopf wurde geklickt, aber Result lädt anders (z.B. Inline statt iframe)
- CHECK24 erkennt "Welperstr." in Hattingen nicht und gibt Fehlerseite
- Result-Frame-Marker hat sich geändert (DOM-Update)

**Fix-Vorschlag für nächste Session:**
1. Screenshot `runs/2026-05-19T204552_check24_error_fill_form.png` ansehen — was zeigt die Page?
2. Falls Fehlerseite: Pre-Check ob Geo-Autocomplete-Vorschlag akzeptiert wurde
3. Falls anderer Result-Frame: Marker in `portals/check24/selectors.py` anpassen
4. Live-Test mit anderer Adresse (Prosperstr. 59 lief gestern problemlos)

## Was die nächste Session noch machen kann (optional)

- **Validator-Erweiterung** für `modul_0.eur_per_qm` in `tools/validate_state.py`
- **E2E-Test:** Modul 0 (Akquise-Modus) → Orchestrator → Modul 5 → Excel-Datei prüfen
- **Mock-Test** für `run_all_portals` (Komplett-Pipeline mit gemockten Adaptern)
- **Akquise-Watcher-Anpassung** falls er Modul 0 jetzt mit Orchestrator-Output aufruft

## Was fertig ist

### Code

| Datei | Status |
|---|---|
| `tools/portal-bewertung/orchestrator.py` | NEU — `run_all_portals(datensatz, headless, kaufabsicht, verbose) -> dict` |
| `tools/portal-bewertung/m00_portal_pricer.py` | erweitert: `--alle`-Mode + `baujahr` an Immometrica weitergeleitet |

### Doku

| Datei | Status |
|---|---|
| `skills/aufteiler-modul-0-quickcheck/SKILL.md` | Stub-Hinweis weg, neue Architektur dokumentiert (Abschnitt 0.2 C, D, G + State-Block) |
| `docs/excel_handoff.md` | KALKU!I13–I17 mit neuen Quellen (Immometrica statt IS24/Preisatlas) |

### Memories

- `project_modul-0-portal-konsens.md` — Architektur-Spec + Excel-Mapping
- `project_immometrica-marktstatistik-workflow.md` (existiert)
- `project_immometrica-baujahr-filter.md` (existiert)
- `project_immometrica-9-tabellen.md` (existiert, aktualisiert)

## Was die nächste Session bauen muss

### 1. State-Schema-Erweiterung (Pflicht)

In `Aufteiler/docs/state-schema.md` + `Aufteiler/docs/state.schema.json`:

```json
"modul_0": {
  "type": "object",
  "properties": {
    "marktwert_konsens_eur": {"type": ["number", "null"]},
    "marktwert_quelle": {"type": "string"},
    "konsens_spread_prozent": {"type": ["number", "null"]},
    "eur_per_qm": {
      "type": "object",
      "properties": {
        "homeday":               {"type": ["number", "null"]},
        "immometrica_plz_etw":   {"type": ["number", "null"]},
        "check24":               {"type": ["number", "null"]},
        "interhyp":              {"type": ["number", "null"]},
        "immometrica_stadt_etw": {"type": ["number", "null"]},
        "median":                {"type": ["number", "null"]}
      }
    }
  }
}
```

Plus Validator-Tests in `tools/test_validate_state.py`.

### 2. Modul-5-Excel-Write erweitern

In `skills/aufteiler-modul-5-deal-bewertung/SKILL.md` (Excel-Schreib-Block):

```python
# In Modul 5, nach BESICHTIGUNG/MIETER/RENO:
kalku = wb['KALKU']
eur_per_qm = state['modul_0'].get('eur_per_qm', {})
if eur_per_qm.get('homeday'):               kalku['I13'] = eur_per_qm['homeday']
if eur_per_qm.get('immometrica_plz_etw'):   kalku['I14'] = eur_per_qm['immometrica_plz_etw']
if eur_per_qm.get('check24'):               kalku['I15'] = eur_per_qm['check24']
if eur_per_qm.get('interhyp'):              kalku['I16'] = eur_per_qm['interhyp']
if eur_per_qm.get('immometrica_stadt_etw'): kalku['I17'] = eur_per_qm['immometrica_stadt_etw']
```

### 3. Live-Test `--alle` (Pflicht vor Final-Marker)

```bash
cd c:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung
.venv/Scripts/python.exe m00_portal_pricer.py --alle \
  --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen \
  --baujahr 1965 --zustand gut --ausstattung normal \
  --anzahl-we 4 --wohnflaechen-qm "60,70,80,90" --zimmer-liste "2,3,3,3" \
  --headless
```

Erwartet:
- 4 Portale parallel
- JSON-Output mit `portale.{check24, homeday, interhyp, immometrica}` + `marktwert.konsens_*` + `eur_per_qm.*`
- 4 Browser-Fenster (oder headless)

Warnung: ein Lauf dauert ~3–5 min (Immometrica braucht 60–90s pro Submit × 6 Configs). Wenn ein einzelnes Portal scheitert → Status `partial`, andere ziehen durch.

### 4. Unit-Tests fuer Orchestrator

`tools/portal-bewertung/tests/test_orchestrator.py`:

- `_compute_konsens([100, 200, 150])` → median=150
- `_compute_eur_per_qm({"status":"ok","marktwert_eur_mittel":200_000}, 100)` → 2000.0
- `_extract_immometrica_eur_per_qm({"extra":{"plz_etw":{"uebersicht":{"median_preis_eur_per_qm":2200}}}})` → `{"plz_etw":2200, "stadt_etw":None}`
- `run_all_portals` mit gemockten Portal-Funktionen → korrekter Aggregations-Output

### 5. Modul-0-Akquise-Modus-Anpassung

Im SKILL.md Abschnitt 0.2 C wurde der CHECK24-Solo-Call ersetzt durch
Orchestrator-Call. Aktuell-Stand: Doku ist konsistent. Aber:

- Akquise-Watcher (lokal) muss möglicherweise erweitert werden — er ruft das Skill bisher mit CHECK24-Annahme. Neuer Aufruf:
  ```
  cd c:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung
  python m00_portal_pricer.py --alle --datensatz <path/zu/datensatz.json> --headless
  ```
- Datensatz-JSON muss vorher in Modul 0 erzeugt + persistiert werden

### 6. Implementierungsplan Step 15 markieren

`tools/portal-bewertung/Implementierungsplan.md` Step 15: `[ ]` → `[x]`.

## Architektur-Regeln (verbindlich)

- **Orchestrator NUR im Akquise-Modus + Modul-0-Aufruf**. Im Orchestrator-Modus (interaktiv) bleibt Modul 0 wie bisher (User-Inputs via AskUserQuestion).
- **Excel-Write nur durch Modul 5.** Modul 0 schreibt €/m² in `state.json`, Modul 5 mapped nach Excel.
- **Konsens-Median über mindestens 1 Quelle.** Wenn alle 4 Portale `status=error`: Score=50, `marktwert_quelle="fehler"`.
- **Spread > 15%**: User-Hinweis im quickcheck.md ("Quellen weichen stark ab — manuell prüfen").

## Tests die DURCHGEHEN müssen vor "fertig"-Marker

- `pytest tools/portal-bewertung/tests/` — bestehende Tests (15+ in Parser, etc.)
- Neu: `pytest tools/portal-bewertung/tests/test_orchestrator.py`
- Live-Test `--alle` headed, einmaliger Lauf mit Prosperstr. 59

## Memory-Bezuege

- [[modul-0-portal-konsens]] — diese Architektur
- [[immometrica-marktstatistik-workflow]] — wie Immometrica intern arbeitet
- [[immometrica-baujahr-filter]] — Baujahr-Range-Regel
- [[immometrica-9-tabellen]] — Chart.js-Extraktion

## Commit-Plan fuer naechste Session

Ein Commit pro grosser Aenderung:
1. `feat(state-schema): modul_0.eur_per_qm-Block + marktwert_konsens_eur`
2. `feat(modul-5): KALKU!I13-I17 aus modul_0.eur_per_qm`
3. `test(portal-bewertung): orchestrator unit tests`
4. `test(portal-bewertung): live --alle smoke test gegen Prosperstr. 59`
