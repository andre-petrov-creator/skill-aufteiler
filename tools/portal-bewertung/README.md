# Portal-Bewertung

Automatisierte Marktwert-Bewertungen von deutschen Immobilien-Portalen
(CHECK24, Homeday, Interhyp, ImmobilienScout24) für den Aufteiler-Workflow.

Sub-Tool des [Aufteiler-Skills](../../skills/aufteiler/SKILL.md), nutzt
Playwright für Browser-Automation und Anthropic-API für Selektor-Recovery
bei DOM-Änderungen.

## Projekt-Dokumente

- [Projektbeschreibung.md](./Projektbeschreibung.md) — Überblick, Stack, Architektur
- [Implementierungsplan.md](./Implementierungsplan.md) — Schritt-für-Schritt MVP-Roadmap
- [CLAUDE.md](./CLAUDE.md) — Steuerungsdatei für Claude Code
- [DEVELOPMENT_GUIDELINES.md](./DEVELOPMENT_GUIDELINES.md) — Code-Style, Testing, Konventionen
- [docs/](./docs/) — Pro-Feature-Doku

## Setup (einmalig)

```powershell
cd C:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
# .env öffnen und ANTHROPIC_API_KEY einsetzen
```

## Lauf (einzelnes Portal)

```powershell
.venv\Scripts\activate
python m00_portal_pricer.py --portal check24 `
  --strasse "Prosperstr." --hausnr 59 --plz 45357 --ort Essen `
  --baujahr 1977 --zustand gut --ausstattung normal `
  --anzahl-we 5 --gesamtwohnflaeche-qm 460 --gesamtzimmer 22 `
  --anzahl-garagen 4 --anzahl-aussenstellplaetze 0 `
  --headless
```

Output: JSON mit `marktwert_eur_min/max/mittel`, drei Trend-Werten,
Ampel-Status und einem fertigen `trend_label`-String für den PDF-Export.

## Lauf (alle Portale parallel)

```powershell
python m00_portal_pricer.py --alle --datensatz datensatz.json --headless
```

Output: aggregiertes JSON mit Median über alle Portale + Spread.

## Tests

```powershell
# Unit-Tests (default, schnell)
pytest

# Live-Tests gegen echte Portale (manuell)
pytest -m "" -v
```

## Status

Aktueller Stand siehe [Implementierungsplan.md](./Implementierungsplan.md).
Erledigte Schritte sind dort mit `[x]` markiert.
