# Projektbeschreibung: Portal-Bewertung

## Überblick

**Was:** Ein Framework + Tool, das aus einem generalisierten MFH-Datensatz
automatisch Marktwert-Bewertungen + Trend-Analysen von mehreren deutschen
Immobilien-Bewertungsportalen abruft (CHECK24, Homeday, Interhyp,
ImmobilienScout24) und einen aggregierten Konsens-Wert zurückgibt.

**Für wen:** Den User selbst — als Sub-Tool des Aufteiler-Workflows (Modul 0
Quick-Check + Modul 5 Deal-Bewertung). Liefert eine **zweite Marktwert-Quelle**
neben dem skill-eigenen ETW-Konsens, damit Bewertungs-Entscheidungen auf
breiterer Datenbasis getroffen werden.

**Warum:**
- Manuelle Portal-Bewertungen (Adresse eingeben, Formular ausfüllen, Werte
  abschreiben) sind langweilig und fehleranfällig. 4 Portale × manuell =
  20 Minuten pro Objekt.
- Skill-eigene Marktwerte basieren auf LLM-Trainings-Wissen — können
  veraltet oder regional ungenau sein. Live-Portal-Daten sind aktuell.
- Trend-Analysen (steigender/fallender Markt) sind preisrelevante Signale,
  die in den finalen Ankaufs-Bericht gehören.

## Tech-Stack

- **Python 3.13** (eigene venv unter `tools/portal-bewertung/.venv/`)
- **Playwright** (Chromium, headless oder headed)
- **Pytest** für Unit-Tests
- **Anthropic-API** für LLM-Fallback (nur bei Selektor-Recovery)
- **JSON** für Output + persistierte gelernte Selektoren
- **Bash/Subprocess** als Integrations-Punkt vom Aufteiler-Skill aus

## Architektur

**Hybrid-Ansatz (Variante C — vom User explizit gewählt):**

1. **Python-Pfad (Default):** Deterministisch, hartcodierte Selektoren,
   0 € Kosten pro Lauf, 100% reproduzierbar
2. **LLM-Fallback bei Selektor-Fail:** Bei DOM-Änderung eines Portals
   wird Claude per Anthropic-API gerufen mit DOM-Dump + Screenshot,
   liefert neuen Selektor, wird persistiert in `learned_selectors/<portal>.json`
3. **Zahlen-Extraktion immer per Regex** — LLM macht NIE Bewertungen
   selbst, nur Navigation. Damit ist Zahlen-Genauigkeit identisch
   über alle Modi.

**Layering:**
- `core/` — Framework, geteilt über alle Portale (Browser, Cookies, Inputs,
  Radios, Submits, Parser, LLM-Recovery)
- `portals/<name>/` — Portal-Adapter, pro Portal ~150 Zeilen, definiert
  Selektoren + Form-Reihenfolge + Result-Frame-Marker
- `orchestrator.py` — ruft mehrere Portale parallel, aggregiert zu
  Konsens-Median
- `m00_portal_pricer.py` — CLI-Entry, `--portal X` oder `--alle`

## Funktionsumfang

### MVP (dieses Projekt)

- ✅ CHECK24-Adapter (bereits MVP-fertig, wird migriert)
- 🔜 Framework-Core extrahiert aus bestehendem CHECK24-Code
- 🔜 Homeday-Adapter (erstes neues Portal nach Migration)
- 🔜 LLM-Recovery für Selektor-Updates
- 🔜 Interhyp-Adapter
- 🔜 ImmobilienScout24-Adapter
- 🔜 Sub-Orchestrator mit Konsens-Median über alle Portale
- 🔜 Modul-0-Integration im Aufteiler-Skill

### Out-of-Scope (bewusst nicht jetzt)

- Cloud-Deployment (Vercel, Hetzner, Browserbase) — User-Entscheidung: lokal
- Sprengnetter / PriceHubble Direct-API
- Captcha-Bypass-Strategien
- Parallelisierung über die 4 Portale hinaus
- Persistente Job-Queue / 24/7-Verfügbarkeit
- Webhook-Trigger aus externer Pipeline

## Architekturentscheidungen (mit Begründung)

| Entscheidung | Begründung |
|---|---|
| **Lokal, kein Cloud-Hosting** | Heim-IP wird von CHECK24 (DataDome) nicht als Bot blockiert. Cloud-IPs werden geblockt. Ausgangslage user-bestätigt. |
| **Hybrid (Python + LLM-Fallback)** | Reines Python ist brüchig bei DOM-Änderungen (alle 3–6 Monate). Reines LLM ist teuer + nicht-deterministisch bei Zahlen. Hybrid: 95% kostenlos + selbstheilend. |
| **Sub-Orchestrator als Python-Tool, nicht als Skill** | Token-leichter für Modul 0 — kein LLM-Reasoning für Orchestrierung, nur Code. Skill bleibt schlank. |
| **Pro Portal ein Adapter, nicht Generic-Form-Filler** | Portale unterscheiden sich genug (iframe vs. direkt, Autocomplete-Patterns, Modal-Reihenfolge), dass ein versuchter Generic-Filler mehr Edge-Cases produziert als hartcodierte Adapter. |
| **Pro Portal manuelles Setup mit Screenshot-Briefing** | User liefert pro neuem Portal Screenshots, wir bauen mit sichtbarem Browser Schritt für Schritt. Schneller als blinder Selektor-Hunt. |
| **`generalisierter_datensatz.py` als zentrale Datenstruktur** | Ein Datensatz, viele Portale. MFH-Durchschnitts-WE-Logik (Wohnfläche, Zimmer, Bäder, 50%-Garage-Regel) wird einmal definiert, alle Portale konsumieren identisch. |
| **Vorsichtige Migration (alte tools/check24/ bleibt parallel)** | Sicherheitsnetz: erst löschen wenn neuer Pfad nachweislich gleiches Ergebnis liefert. |

## Skill-Referenzen

- `superpowers:test-driven-development` — Tests schreiben **vor** Implementierung
  (für `core/`-Module wichtig)
- `superpowers:systematic-debugging` — Bei Live-Lauf-Problemen
- `aufteiler-modul-0-quickcheck` — Konsument des Sub-Orchestrators (Phase 6)
- `aufteiler-modul-5-deal-bewertung` — zeigt Portal-Werte im PDF (Phase 6)

## Datenfluss (End-to-End)

```
Modul 0 Quick-Check
   │
   │ subprocess: python m00_portal_pricer.py --alle <datensatz.json>
   ▼
orchestrator.py
   │
   ├──► Check24Portal.run()    ─────┐
   ├──► HomedayPortal.run()    ─────┤
   ├──► InterhypPortal.run()   ─────┤
   └──► ImmoScout24Portal.run() ────┤
                                    ▼
                            Aggregator (Median + Spread)
                                    │
                                    ▼
                    JSON: { portale: {...}, konsens_marktwert_eur, konsens_label }
                                    │
                                    ▼
                            zurück an Modul 0
                                    │
                                    ▼
                            State: modul_0.portal_bewertungen
                                    │
                                    ▼
                            Modul 5 PDF-Export
```

## Erfolgs-Kriterien (Definition of Done)

1. CHECK24-Adapter im neuen Framework liefert gleiches Ergebnis wie alte
   `tools/check24/` (Live-Lauf Prosperstr. 59 → ~173.000–175.000 €)
2. Mindestens 3 weitere Portale (Homeday, Interhyp, IS24) produktiv
3. LLM-Recovery beweisbar: künstlicher Selektor-Bruch wird automatisch
   gelernt und gefixt
4. Sub-Orchestrator gibt Konsens-Median über alle 4 Portale aus
5. Modul 0 nutzt den Konsens-Median als zweite Marktwert-Quelle
6. Alle `core/`-Module haben Unit-Tests (kein Test pro Portal-Selektor
   — die werden live verifiziert)

## Ablage & Repo-Position

Diese Doku liegt unter:
`C:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung\`

Teil des Mono-Repos `meine-projekte` (GitHub: `andre-petrov-creator/meine-projekte`).
Verwandte Pfade:
- Ursprung: `tools/check24/` (wird in Phase 2 in dieses Framework migriert)
- Konsument: `skills/aufteiler-modul-0-quickcheck/SKILL.md`
- Konsument: `skills/aufteiler-modul-5-deal-bewertung/SKILL.md`
