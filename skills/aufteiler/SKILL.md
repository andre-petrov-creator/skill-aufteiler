---
name: aufteiler
description: Orchestrator für die MFH-Aufteiler-Analyse (NRW/Ruhrgebiet). Trigger bei "Aufteiler", "Vollanalyse MFH", "Quick-Check MFH", "Mietsituation prüfen", "RND prüfen", "AfA-Frage", "lohnt sich ein RND-Gutachten", "Modernisierungspunkte", "Kaufpreisaufteilung", "Massnahmen kalkulieren", "Deal-Bewertung", "PDF-Export Aufteiler". Erkennt Modus deterministisch, legt State pro Objekt an, dispatcht Modul-Sub-Skills. Ab Modul 2 hartes AskUserQuestion-Gate nach JEDEM Modul — durch keine User-Formulierung ("Vollanalyse", "von A bis Z") im Voraus abwählbar. Rechnet selbst NICHTS.
---

> **Schritt 0 - Aktualisierung (vor allem anderen, ohne Rückfrage):** Führe diesen einen Befehl aus:
> `git -C "C:/meine-projekte/Immobilien/Aufteiler" rev-parse HEAD; git -C "C:/meine-projekte/Immobilien/Aufteiler" pull --ff-only -q; git -C "C:/meine-projekte/Immobilien/Aufteiler" rev-parse HEAD`
> Sind die beiden ausgegebenen Hashes verschieden, wurde der Skill gerade aktualisiert: lies diese SKILL.md vollständig neu
> und arbeite mit der neuen Fassung. Schlägt der Befehl fehl (offline, lokale Änderungen), ignoriere das still und arbeite weiter.

# Aufteiler-Orchestrator

Stumpfer Dispatcher. Je dümmer, desto reproduzierbarer.

**Stand 2026-05-26 (Konsolidierungs-Refactor):** Modul 0 = `aufteiler-modul-0-akquise-automatisierung` (CRM/Mail-Pipeline, vom Watcher angestoßen). Modul 1 = `aufteiler-modul-1-auto-analyse` (vollautomatische Analyse, läuft nach Modul 0 oder eigenständig manuell). Module 2–6 = `objektbasis`/`rnd-afa`/`massnahmen`/`miete`/`deal-bewertung` (manuell durchgeklickt mit Freigabe-Gates). Siehe Plan `~/.claude/plans/kannst-du-nochmal-kurz-validated-wand.md`.

## 1. Modus-Erkennung (deterministisch — keine Vermutung)

Erste Aktion bei jedem Aufruf: User-Aussage gegen Tabelle matchen.

| User sagt … (Substring-Match, case-insensitive) | Modus | Sequenz |
|-------------------------------------------------|-------|---------|
| "vollanalyse", "komplette analyse", "alles", "ganze analyse", "von a bis z", "komplett durchanalysieren", "bis zum schluss" | `vollanalyse` | 1 → 2 → 3 → 4 → 5 → 6 |
| "auto-analyse", "automatische analyse", "quick-check", "quickcheck", "schnellcheck" | `nur_auto_analyse` | 1 |
| "objektbasis", "we-liste", "we liste" | `nur_basis` | 2 |
| "rnd", "restnutzungsdauer", "afa" — mit Objekt-Analyse-Auftrag | `nur_rnd` | 3 |
| Frage oder Ersteinschätzung zu RND/AfA/Modernisierungspunkten/Kaufpreisaufteilung ohne Auftrag zur Objekt-Analyse („lohnt sich ein RND-Gutachten bei …?", „zählt …?", „was ist die 15-%-Regel?") | `afa_frage` | Modul 3 Sektion 8, ohne State/Gates |
| "massnahmen", "sanierung", "modernisierung" | `nur_massnahmen` | 4 |
| "miete", "mietspiegel", "mietsituation" | `nur_miete` | 5 |
| "deal-bewertung", "pdf-export", "pdf export", "endbericht", "verdict" | `nur_export` | 6 |
| "akquise", "akquise-automatisierung", "mail-pipeline re-run" | `nur_akquise` | 0 |

**Modul 0 (Akquise-Automatisierung) läuft normalerweise NICHT manuell** — der Watcher (`watch-inbox.ps1`) ist der einzige reguläre Caller. Manueller Trigger nur für Re-Runs eines bereits eingegangenen Leads (z.B. wenn Pipeline-Lauf abgebrochen ist).

**Modus `afa_frage`:** kein Slug, kein State, kein TodoWrite, keine Gates. Direkt `Skill(skill="aufteiler-modul-3-rnd-afa", args="afa_frage: <Frage + Objektangaben>")` — das Modul antwortet aus seiner Wissensbasis (Sektion 8). Unterschied zu `nur_rnd`: dort wird ein konkretes Objekt mit State + RND-Freeze analysiert.

**Bei unklarem Input** (kein Match oder mehrere Matches): EINE Rückfrage via `AskUserQuestion` mit allen plausiblen Modi als Optionen. Niemals raten.

**Der Modus definiert NUR die geplante Modul-Sequenz — niemals die Freigaben.** Auch `vollanalyse` läuft Modul für Modul mit hartem Gate nach jedem Modul ab Modul 2 (Sektion 5). Es gibt KEINE Formulierung, die die Gates im Voraus abwählt.

## 2. TodoWrite VOR Start

Sobald Modus erkannt, sofort `TodoWrite` aufrufen mit einer Aufgabe pro Modul der Sequenz + zwei Klammer-Aufgaben:
- "State init / laden für Objekt <slug>"
- "Modul 1 — Automatische Analyse"
- … (gemäß Sequenz, z.B. „Modul 2 — Objektbasis", „Modul 3 — RND/AfA", etc.)
- "Vollanalyse abgeschlossen"

Damit ist State auch nach Compression sichtbar, und Claude kann nicht „springen".

## 3. Objekt-Slug + State-Init

1. **Adresse erfragen** via `AskUserQuestion`, falls nicht im Input enthalten:
   "Adresse des Objekts? (z.B. Vestische Straße 250, 46145 Oberhausen-Sterkrade)"
2. **Slug bilden:** lesbares Adress-Format `<Straße (ausgeschrieben)> <Hausnummer>, <PLZ> <Ort>[-<Stadtteil>]`. Detail-Regeln:
   - „Str." → „Straße" (nur dieses Suffix normalisieren; Allee/Platz/Ring/Weg bleiben)
   - ß und Umlaute bleiben original
   - Hausnummern-Buchstabe lowercase (`44a`), Range immer mit Bindestrich (`44-45`, nie `44/45`)
   - Apostroph, Klammern, `&` weglassen
   - Fallback bei unbekannter Adresse: `unbekannt - <msg-id-short>`

   Beispiele:
   - `Prosperstr. 59, 45356 Essen-Dellwig` → `Prosperstraße 59, 45356 Essen-Dellwig`
   - `Vestische Straße 250, 46145 Oberhausen-Sterkrade` → `Vestische Straße 250, 46145 Oberhausen-Sterkrade`
   - `Welperstr. 39, 45525 Hattingen` → `Welperstraße 39, 45525 Hattingen`

   Legacy-Slugs (kebab-case wie `prosperstr-59-essen-dellwig`) existieren weiterhin in `runs/` für alte Leads — der Validator akzeptiert beide Formate, neue Leads bekommen das Adress-Format.
3. **Bestehenden State suchen:** `runs/<slug>/state.json` lesen. Falls im Root nicht vorhanden, in `runs/<slug>/.aufteiler/state.json` nachsehen — dorthin verschiebt der finale Cleanup den State, wenn ein Lead ruht. **Wenn in `.aufteiler/` gefunden: zuerst `state.json` + `objektdaten.json` zurück ins Root holen** (`runs/<slug>/`), damit die Module 2–6 wie gewohnt im Root arbeiten. Wenn vorhanden:
   - `objekt.letzter_modul_lauf` melden: `"State für <slug> existiert, letzter Lauf: <modul_N>. Weiter ab Modul <N+1>? (ja = weiter, neu = State frisch)"`
   - User-Antwort `neu` → existierenden Ordner zu `runs/<slug>_<timestamp>_archiv/` umbenennen, frischen anlegen.
4. **Frischen State init** (falls neu oder nach Archiv):
   ```bash
   mkdir -p runs/<slug>/eingangs-daten
   ```
   `runs/<slug>/state.json` mit Minimal-Objekt:
   ```json
   {
     "schema_version": "2.0",
     "objekt": {
       "slug": "<slug>",
       "adresse": "<adresse>",
       "stadt": "<stadt>",
       "bundesland": "NRW",
       "erstellt_am": "<heute ISO>",
       "letzter_modul_lauf": "modul_1"
     }
   }
   ```
5. Validieren: `python tools/validate_state.py runs/<slug>/state.json` → exit 0.

## 4. Sub-Skill-Aufruf pro Modul (Sequenz abarbeiten)

Pro Sequenz-Schritt:

1. Todo-Item auf `in_progress` setzen.
2. Sub-Skill via `Skill`-Tool aufrufen:
   - **Modul 0 (CRM-Akquise-Pipeline, nur Re-Run):** `Skill(skill="aufteiler-modul-0-akquise-automatisierung", args="<ordner_pfad>")` — Mail-Triage, Link-Fetch, Duplikat-Check, Drei-Schichten-Ordner-Sortierung, Supabase-Lead. Reguläre Caller ist der Watcher, manueller Aufruf nur bei `nur_akquise`-Modus.
   - **Modul 1 (Automatische Analyse):** `Skill(skill="aufteiler-modul-1-auto-analyse", args="<objekt_slug>")` — Tiefen-Extraktion `objektdaten.json`, BORIS + 4 Portale + GMB + Mietspiegel, 5-Sub-Score (Lage 6-dim), Eckdaten, Cashflow. Läuft autark, Modul-0-Vorlauf nicht erforderlich.
   - **Modul 2 (Objektbasis):** `Skill(skill="aufteiler-modul-2-objektbasis", args="<objekt_slug>")`
   - **Modul 3 (RND/AfA):** `Skill(skill="aufteiler-modul-3-rnd-afa", args="<objekt_slug>")`
   - **Modul 4 (Massnahmen):** `Skill(skill="aufteiler-modul-4-massnahmen", args="<objekt_slug>")`
   - **Modul 5 (Miete):** `Skill(skill="aufteiler-modul-5-miete", args="<objekt_slug>")`
   - **Modul 6 (Deal-Bewertung):** `Skill(skill="aufteiler-modul-6-deal-bewertung", args="<objekt_slug>")`
3. Nach Sub-Skill-Rückkehr: State neu lesen, prüfen ob `objekt.letzter_modul_lauf` korrekt hochgesetzt wurde. Wenn nein → Fehler an User: "Modul N hat State nicht geschrieben."
4. Todo-Item auf `completed` setzen.
5. **Pflicht-Visualisierung prüfen** (siehe 5a) — der komplette Zonen-Output muss im Chat stehen, BEVOR das Gate gestellt wird.
6. **Hartes Freigabe-Gate** (siehe 5).

## 5. Hartes Freigabe-Gate (Pflicht nach JEDEM Modul ab Modul 2)

**Schicht A ohne Gate:** Modul 0 und Modul 1 laufen automatisch durch (Akquise / Auto-Analyse) — zwischen 0 und 1 kein Gate. Nach Modul 1 endet die Automatik: Quick-Check zeigen, danach geht es nur auf User-Anstoß weiter.

**Schicht B (Module 2–6): Nach JEDEM Modul ein hartes Gate.** Ablauf pro Gate:

1. Pflicht-Visualisierung ist gerendert (Sektion 5a) — sonst Gate nicht stellen, erst rendern.
2. Gate via `AskUserQuestion` (klickbar — NIE als Freitext-Frage im Chat):
   - Frage: `Modul N (<Name>) abgeschlossen — wie weiter?`
   - Option 1: `Weiter zu Modul N+1 (<Name>)`
   - Option 2: `Korrektur an Modul N` → User nennt die Korrektur, Modul N läuft damit erneut, danach wieder Visualisierung + Gate
   - Option 3: `Stopp` → Sequenz stoppen: "Stopp. State ist persistiert. Weiter mit `<objekt-slug> weiter` möglich."
   (Nach Modul 5 heißt Option 1 `Weiter zu Modul 6 (Deal-Bewertung)`; Excel/PDF haben darin nochmal eigene Freigaben.)

**DAS GATE IST DURCH KEINE USER-FORMULIERUNG IM VORAUS ABWÄHLBAR. Aussagen wie „Vollanalyse", „alles durchlaufen", „komplett von A bis Z", „bis zum Schluss durchanalysieren", „einmal komplett durchziehen" definieren NUR die geplante Modul-Sequenz — sie ersetzen NIEMALS die Einzel-Freigaben. Es gibt KEINE Formulierung, die alle Gates auf einmal freischaltet.**

Rationalisierungs-Sperre — jeder dieser Gedanken bedeutet: STOPP, Gate trotzdem stellen:

| Gedanke | Realität |
|---------|----------|
| „User hat doch ‚von A bis Z' gesagt" | Definiert die Sequenz, nicht die Freigaben. |
| „Gate nervt bei expliziter Vollanalyse" | Das Gate ist die einzige Korrektur-Chance, bevor Folgemodule auf den Werten weiterrechnen. |
| „Ich frage am Ende einmal gesammelt" | Zu spät — am Ende steht die Excel fertig da, Korrigieren praktisch unmöglich (Datteln-Lauf 2026-06-11). |
| „User ist erfahren, der meldet sich schon" | Ohne Visualisierung + Gate gibt es nichts, woran er Fehler erkennen könnte. |

**Typischer Einstieg:** Der User steigt meist ab Modul 2 händisch ein und geht die Module gemeinsam mit Claude durch — pro Modul: Output ansehen, ggf. korrigieren, klickbar freigeben.

## 5a. Pflicht-Visualisierung VOR jedem Gate

Grundsatz: **Alles, was später in PDF oder Excel landet, hat der User vorher Modul für Modul im Chat gesehen.**

Nach jedem Modul-Lauf (Module 2–6) MUSS im Chat stehen — 1:1 identisch zu dem, was das Modul in seine Audit-Datei `runs/<slug>/modul-N-output.md` geschrieben hat:

- **Zone A komplett** — alle Datenblöcke als Markdown-Tabellen
- **Zone B** — Tiefenstufen-Deklaration (beide Zeilen)
- **Zone C komplett** — Annahmen / Risiken / Empfehlung
- **Excel-Transfer-Vorschau** — Tabelle `Sheet!Zelle | Wert`: welche Zellen die Werte dieses Moduls später (via Modul 6) befüllen

Das Rendern übernimmt das Modul selbst (Sektion 7 der Modul-Skills). **Kontroll-Pflicht des Orchestrators:** Hat ein Modul nur einen Einzeiler geliefert, rendert der Orchestrator den kompletten Zonen-Output aus der Audit-Datei nach, BEVOR er das Gate stellt. Ein Einzeiler im Chat ist NIE ausreichend — auch nicht bei „Vollanalyse".

## 5b. Nach Sequenz-Ende: Ordner aufräumen (Pflicht)

Sobald die geplante Sequenz endet — letztes Modul der Sequenz abgeschlossen ODER User wählt im Gate „Stopp" — den Lead-Ordner ins Soll-Layout bringen:

```bash
python tools/cleanup_lead_folder.py "<lead-ordner-pfad>" --final
```

`--final` heißt: Lead ruht nach diesem Schritt — auch `state.json` + `objektdaten.json` wandern nach `.aufteiler/` (zusammen mit `modul-*-output.md`, `*.py`, Scraper-Dumps). **Sichtbar im Root bleiben:** `quickcheck.md`, `README.md`, `Kalkulation_*.xlsx`, `Aufteiler_*.pdf` + die 4 Schlüssel-Dokumente + `Bilder/` + `Unterlagen/`. Bei der nächsten Wiederaufnahme holt Sektion 3 den State aus `.aufteiler/` zurück ins Root. Idempotent + OneDrive-Lock-robust (kein Hard-Fail). Details: `docs/modul_0_ordnerstruktur.md`. Modul 0/1 räumen im Watcher-Pfad selbst final auf — der erneute Aufruf hier ist idempotent.

## 6. Fragen nach Abschluss → Pflicht-Read

Wenn User nach Sequenz-Ende eine Frage stellt („Wie hoch war die Sollmiete für WE 3?"), NIE aus dem Chat antworten. Immer `Read runs/<slug>/state.json` (bleibt im Root) oder `Read runs/<slug>/.aufteiler/modul-N-output.md` (liegt nach dem Aufräumen dort) ausführen und Wert daraus zitieren.

## 7. Was der Orchestrator NICHT macht

- Keine Berechnungen.
- Keine Excel-Befüllung (das macht Modul 6 — nach eigener Werte-Vorschau + Freigabe).
- Keine Interpretation von Modul-Outputs.
- Keine Modus-Schätzung bei mehrdeutigem Input.
- Kein Override von Modul-Status (wenn Modul rot meldet, Sequenz stoppt).
- **Kein Überspringen von Gates oder Visualisierungen** — egal welche Formulierung der User vorab benutzt hat.

============================================================

## Änderungen

- **2026-06-15 — Ordner-Aufräum-Standard** (Sektion 5b neu): Nach Sequenz-Ende ruft der Orchestrator `tools/cleanup_lead_folder.py` — Arbeits-/Zwischendateien nach `.aufteiler/`, `Bilder/` sichtbar; `state.json`/`objektdaten.json`/`quickcheck.md`/`README.md`/Excel/PDF + 4 Schlüssel-Dokumente bleiben im Root. Sektion 6 liest `modul-N-output.md` jetzt aus `.aufteiler/`. Modul 0/1 räumen im Watcher-Pfad selbst auf (idempotent).
- **2026-06-11 — Gate-Härtung + Pflicht-Visualisierung** (nach Datteln-Lauf, `plans/2026-06-11-orchestrator-gate-haertung-visualisierung.md`): Freigabe-Gate von Freitext (`go`/`weiter`/`ja`/`ok`) auf hartes `AskUserQuestion` mit Optionen Weiter/Korrektur/Stopp umgestellt; Anti-Override-Regel (keine User-Formulierung wählt Gates im Voraus ab) + Rationalisierungs-Sperre; neue Sektion 5a Pflicht-Visualisierung (Zonen A/B/C + Excel-Transfer-Vorschau 1:1 im Chat vor jedem Gate, Orchestrator rendert nach wenn Modul nur Einzeiler liefert); Sektion-7-Fix: Excel-Befüllung macht Modul 6, nicht Modul 5.
