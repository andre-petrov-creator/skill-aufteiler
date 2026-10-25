# Development Guidelines: Portal-Bewertung

## Code-Style

### Allgemein

- **Python ≥ 3.13.** Type-Hints durchgängig.
- **Black-konform** (Linienlänge 100). Kein Formatter erzwungen, aber
  Stil daran orientieren.
- **Docstrings:** Module-Header + public-Funktionen. Kurz, Zweck-orientiert.
  Kein doc-block-überladenes Zeugs.
- **Keine Kommentare im Code außer bei nicht-offensichtlichem WHY.**
  Lesbarer Code statt Erklärungen.
- **Keine Schein-Robustheit.** Kein `try: ... except: pass` zum
  Schweigen-Bringen. Fehler explizit machen, Screenshot capturen, Error-JSON.

### Naming

- **Variablen, Funktionen, Files:** `snake_case`
- **Klassen:** `PascalCase`
- **Konstanten:** `UPPER_SNAKE_CASE`
- **Private Funktionen:** Unterstrich-Prefix `_helper_function`
- **Domänen-Begriffe bleiben Deutsch:** `marktwert_eur_mittel`,
  `zustand`, `ausstattung`, `anzahl_we`, `wohnflaeche_qm`. Nicht
  übersetzen — sie matchen die Skill-Sprache und das Excel-Mapping.

## Architektur

### Folder-Struktur

```
tools/portal-bewertung/
├── core/                # FRAMEWORK — portal-agnostisch
├── portals/<name>/      # PORTAL-ADAPTER — portal-spezifisch
├── inspectors/          # DEV-TOOLS — DOM-Dumper, einmalig genutzt
├── tests/               # UNIT-TESTS für core/
├── docs/                # PRO-FEATURE-DOKU (Pflicht!)
├── runs/                # Screenshots (gitignored)
├── learned_selectors/   # LLM-gelernte Selektoren (gitignored)
└── m00_portal_pricer.py # CLI-Entry
```

### Verantwortlichkeiten

- **`core/`** darf **nicht** Portal-Namen kennen. Keine `if portal ==
  "check24": ...`-Logik.
- **`portals/<name>/`** darf nur seine eigenen Selektoren + Klasse
  enthalten. Keine `core/`-Logik dupliziert.
- **`m00_portal_pricer.py`** ist nur ein CLI-Wrapper. Geschäftslogik in
  `orchestrator.py` und `core/runner.py`.

### Dependency-Richtung

- `portals/*` darf `core/*` importieren
- `core/*` darf **NICHT** `portals/*` importieren
- `tests/*` darf alles importieren
- `inspectors/*` darf `core/*` importieren (aber meistens standalone)
- `m00_portal_pricer.py` + `orchestrator.py` dürfen alles importieren

### Klassen vs. Funktionen

- **Klassen** nur für `PortalBase` und dessen Subklassen — sie haben
  Identität (`NAME`, `START_URL`) und vererben.
- **Alles andere als Funktionen.** Kein OO-Wahn. Wenn eine Klasse nur
  Daten hält → `@dataclass`.

## Testing

### Was wird getestet

| Modul | Test-Strategie | Pflicht? |
|---|---|---|
| `core/datensatz.py` | Unit-Tests, reine Logik | ✅ |
| `core/parsers.py` | Unit-Tests mit Beispiel-Texten | ✅ |
| `core/modals.py` | Unit-Tests, mocked Page-Objekt | ✅ |
| `core/inputs.py`, `radios.py`, `submit.py` | Sehr wenig — schwer zu mocken | ✗ (Live-Test reicht) |
| `core/runner.py` | Smoke-Test mit Dummy-Portal | ✅ |
| `core/llm_recovery.py` | Unit-Test mit mocked Anthropic-Client | ✅ |
| `portals/<name>/` | **KEIN Unit-Test pro Portal-Selektor.** Stattdessen `@pytest.mark.slow` Live-Test gegen echte Seite | Optional, manuell |
| `orchestrator.py` | Unit-Test mit gemockten Portal-Klassen | ✅ |

### Test-Konventionen

- **File-Naming:** `tests/test_<modul>.py`
- **Test-Naming:** `def test_<feature>_<szenario>():`
- **Marker für Live-Tests:** `@pytest.mark.slow` + `pytest.ini` schließt
  sie per `addopts = -m "not slow"` aus dem Default-Run aus
- **Mocks:** `unittest.mock` für Anthropic-Client; Playwright-Page
  per Dummy-Klasse mocken (keine echten Browser in Unit-Tests)

### Test-Ausführung

```bash
# Default — nur Unit-Tests
pytest

# Inklusive Live-Tests gegen echte Portale (manuell!)
pytest -m "" -v

# Nur ein bestimmtes Modul
pytest tests/test_core_parsers.py -v
```

## Git-Workflow

- **Branch:** Direkt auf `main` für eigene Repos (User-Konvention).
- **Commit-Messages:** `<type>(portal-bewertung): <kurze Beschreibung>`
  wo `<type>` in `{feat, fix, docs, refactor, test, chore}`
- **Commit-Granularität:** Pro Step des Implementierungsplans 1 Commit.
  Mehrere Commits pro Step nur bei großen Steps (z.B. Step 5 mit 7
  Modulen).
- **Push:** Nach jedem Commit auf `main` push, damit GitHub als
  Backup aktuell ist.
- **Kein `--no-verify`, kein `--force-push`** ohne explizite User-Anweisung.

## Externe Dependencies

### Erlaubt ohne Rückfrage

- Stabile, weit verbreitete Libs aus dem PyPI-Top-100
- Bereits im Projekt vorhandene Libs (playwright, pytest, anthropic,
  python-dotenv)

### Rückfrage nötig

- Anti-Bot-Bypass-Libs (`playwright-stealth`, `undetected-chromedriver`,
  ...) — User entscheidet, ob das Risiko in Kauf genommen wird
- Neue ML/AI-SDKs außer dem etablierten Anthropic-SDK
- Libs mit < 1000 GitHub-Stars oder älter als 2 Jahre ungepflegt

### Verboten

- Proxy-Provider-SDKs (Brightdata, Oxylabs, ...) — Cloud-Architektur
  explizit ausgeschlossen
- Web-Frameworks (FastAPI, Flask, Django) — kein Server-Setup geplant
- DB-Libs (SQLAlchemy, peewee, ...) — JSON-Files reichen

## Output-Schema (verbindlich)

Jeder Portal-Run liefert ein JSON mit diesen Pflichtfeldern:

```json
{
  "status": "ok" | "error",
  "portal": "check24" | "homeday" | "interhyp" | "immoscout24",
  "marktwert_eur_min": <int|null>,
  "marktwert_eur_max": <int|null>,
  "marktwert_eur_mittel": <int|null>,
  "trends": {
    "jahre_3": <float|null>,
    "jahr_1": <float|null>,
    "prognose": <float|null>
  },
  "trend_ampel": "gruen" | "gelb" | "rot" | null,
  "trend_ampel_label": <string|null>,
  "trend_label": <string|null>,
  "url": <string>,
  "timestamp": <ISO8601>,
  "screenshot_path": <string|null>,
  "generalisierter_datensatz": { ... }
}
```

Bei `status: "error"`: zusätzlich `error_code`, `error_message`.

**Brechen dieses Schemas erfordert Update von Modul 0 + Modul 5.**

## Logging

- Zentrale `_log(msg)` Funktion (siehe `core/log.py` ab Step 5)
- Default: stumm (keine Ausgabe)
- Mit `--verbose` oder `cfg.verbose=True`: Logs auf **stderr** (nicht stdout,
  sonst zerschießt's das JSON)
- Kein `print()` direkt im Code, immer `_log()`

## Error-Handling

- **Niemals silent except.** Jeder Fehler wird:
  1. Screenshot capturen (`runs/<timestamp>_error_<step>.png`)
  2. Strukturiertes Error-JSON zurückgeben
  3. Exit-Code 1
- **Bei Selektor-Fail in `core/runner.py`:** LLM-Recovery automatisch
  triggern (Phase 11). Wenn Recovery erfolgreich → weiter. Wenn nicht →
  Error-JSON.

## Performance-Erwartungen

- **Ein Portal-Lauf:** ~30 Sekunden (Browser-Start, Form, Submit, Read).
- **Alle 4 Portale parallel:** ~45 Sekunden (parallele Chromium-Instanzen).
- **Mit LLM-Recovery (DOM-Bruch):** +10 Sekunden, einmalig pro Portal,
  bis Selektor gelernt ist.

## Sicherheits-Hinweise

- **ANTHROPIC_API_KEY:** Nur in `.env`, niemals committed. `.env`
  steht in `.gitignore`, `.env.example` ist die Vorlage.
- **Adressdaten:** Bleiben auf User-PC. Werden nicht an Anthropic
  geschickt (nur DOM-Strukturen bei Recovery).
- **Screenshots:** Können sensible Daten enthalten — `.gitignore` filtert
  `runs/*.png` aus.
