# Projekt: Portal-Bewertung

Sub-Tool des Aufteiler-Skills. Holt Marktwert-Bewertungen von mehreren
deutschen Immobilien-Portalen (CHECK24, Homeday, Interhyp, ImmobilienScout24)
automatisiert ab und liefert einen Konsens-Median.

## Vor jeder Aufgabe

1. Lies [Projektbeschreibung.md](./Projektbeschreibung.md) — Architektur,
   Stack, Out-of-Scope
2. Lies [DEVELOPMENT_GUIDELINES.md](./DEVELOPMENT_GUIDELINES.md) — Code-Style,
   Testing-Konventionen, Folder-Struktur
3. Lies relevante Dateien in [docs/](./docs/) — pro Feature eine Doku
4. Lies [Implementierungsplan.md](./Implementierungsplan.md) — wo sind
   wir gerade, was ist abgehakt
5. Referenziere installierte Skills:
   - `superpowers:test-driven-development` (für `core/`-Module)
   - `superpowers:systematic-debugging` (bei Live-Lauf-Problemen)
   - `aufteiler-modul-0-quickcheck` (Konsument, Phase 6)
   - `aufteiler-modul-5-deal-bewertung` (Konsument, Phase 6)

## Nach jeder Aufgabe

1. Aktualisiere oder erstelle `docs/[feature].md` mit:
   - **Zweck:** Was macht das Feature/Modul
   - **Files:** Welche Dateien gehören dazu
   - **Datenfluss:** Wie Daten durchlaufen
   - **Schnittstellen:** APIs, Hooks, exportierte Funktionen
   - **Bekannte Limitierungen:** Edge-Cases, TODOs, technische Schulden
2. Halte Code-Style und Konventionen aus GUIDELINES ein
3. Schreibe oder aktualisiere Unit-Tests in `tests/` (für `core/`-Module
   zwingend, für Portal-Adapter nicht — die werden live verifiziert)
4. Update [Implementierungsplan.md](./Implementierungsplan.md): Schritt
   N als `[x]` markieren
5. Commit-Message-Konvention: `feat(portal-bewertung): <kurze
   Beschreibung>` oder `fix(portal-bewertung): ...` oder
   `docs(portal-bewertung): ...`

## Stack

- **Python 3.13+** (eigene venv unter `.venv/`)
- **Playwright** (Chromium, headless oder headed)
- **Pytest** für Unit-Tests
- **Anthropic-API** (`anthropic` Python-SDK) — nur für LLM-Recovery bei
  Selektor-Fail, nicht im Hauptpfad
- **python-dotenv** für `.env`-Laden (ANTHROPIC_API_KEY)

## Architektur-Prinzipien

1. **Hybrid: Python deterministisch + LLM-Fallback nur bei Selektor-Fail.**
   95% der Läufe ohne LLM-Aufruf, 0 € Kosten, voll reproduzierbar.
2. **Zahlen IMMER per Regex.** LLM macht NIE Bewertungen selbst, nur
   Navigation. Damit ist Marktwert-Genauigkeit identisch über alle
   Modi.
3. **Layering strikt:**
   - `core/` — wiederverwendbar über alle Portale, portal-agnostisch
   - `portals/<name>/` — portal-spezifisch (Selektoren, Form-Reihenfolge)
   - Keine Portal-spezifische Logik in `core/`. Keine Framework-Logik
     in `portals/`.
4. **Pro Portal eine kleine Adapter-Klasse** (PortalBase-Subklasse),
   nicht ein Generic-Form-Filler. Portale unterscheiden sich genug,
   dass Adapter sauberer ist.
5. **Selektoren persistiert lernbar:** Bei DOM-Änderung lernt das Tool
   den neuen Selektor via LLM, speichert ihn in
   `learned_selectors/<portal>.json`. Beim nächsten Lauf wird der
   gelernte Selektor vor dem hartcodierten probiert.
6. **Lokal-only.** Heim-IP bleibt unauffällig. Kein Cloud-Deployment.
7. **JSON-Output strikt schema-konform.** Modul 0 konsumiert das Schema —
   Brechen verboten.

## Konventionen

- **Sprache im Code:** Englisch (Variablen, Funktionen, Klassen,
  Commit-Messages)
- **Ausnahmen:** Fachbegriffe wie `marktwert_eur_mittel`, `zustand`,
  `ausstattung`, `anzahl_we` bleiben Deutsch — sie sind Teil des
  Domänen-Modells und matchen die Skill-Sprache
- **Naming:** snake_case für Python (Variablen, Funktionen, Files),
  PascalCase für Klassen
- **File-Struktur:** Siehe `Projektbeschreibung.md` "Ziel-Verzeichnisstruktur"
- **Type-Hints:** Pflicht für alle public-Funktionen in `core/` und
  alle CLI-Argumente in `m00_portal_pricer.py`
- **Docstrings:** Pflicht für Module + public-Funktionen (kurz, Zweck +
  Hauptparameter)
- **Logging:** Über `core/log.py` zentral, nicht print(). Verbose-Flag
  schaltet Logs auf stderr.
- **Test-Konvention:** `tests/test_core_<modul>.py` für Framework,
  `@pytest.mark.slow` für Live-Tests gegen echte Portale (laufen
  manuell, nicht in CI)

## Wichtige Pfade

| Pfad | Zweck |
|---|---|
| `core/` | Framework-Code (datensatz, parsers, playwright-helpers, runner) |
| `portals/` | Portal-Adapter pro Portal (check24, homeday, interhyp, immoscout24) |
| `tests/` | Unit-Tests für `core/` |
| `inspectors/` | Dev-Tools: DOM-Dumper für neue Portale |
| `learned_selectors/` | Persistierte Selektoren vom LLM-Recovery (gitignored) |
| `runs/` | Screenshots aller Läufe (gitignored, außer `.gitkeep`) |
| `docs/` | Pro-Feature-Doku (Pflicht nach jeder Aufgabe) |
| `.venv/` | Python venv (gitignored) |
| `.env` | ANTHROPIC_API_KEY (gitignored, `.env.example` als Template) |

## Aufrufe von außen

Modul 0 ruft das Tool per Bash:

```bash
python tools/portal-bewertung/m00_portal_pricer.py \
  --alle \
  --datensatz tools/portal-bewertung/runs/datensatz.json \
  --headless
```

Output ist strukturiertes JSON auf stdout, das Modul 0 parsen kann.

## Was NICHT in dieses Tool gehört

- Bewertungs-Logik (Konsens, gap-Check etc.) — gehört in Modul 0
- PDF-Generierung — gehört in Modul 5 / pdf-export-Skill
- Adress-Extraktion aus Exposé — gehört in Modul 0
- Mietspiegel-Lookups — gehört in Modul 4

Dieses Tool ist ein **dummer Marktwert-Lieferant**. Es bekommt einen
fertigen `GeneralisierterDatensatz`, gibt Portal-Werte zurück. Mehr nicht.
