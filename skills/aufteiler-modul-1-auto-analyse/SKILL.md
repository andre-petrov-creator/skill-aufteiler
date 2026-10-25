---
name: aufteiler-modul-1-auto-analyse
description: Modul 1 der Aufteiler-Analyse — Automatische Analyse (v3.8, 2026-09-10 — Status-Gate pro Immometrica-Config in Schritt 5.2: nur `status == "ok"` liefert Werte, `geo_mismatch`/`geo_not_set`/`stale_heading` gelten als fehlend. Grund: ohne gesetzten Ort-Filter liefert Immometrica bundesweite Zahlen, die der Adapter vor dem Fix als PLZ-Werte gemeldet hat; v3.7, 2026-06-25 — Sub-Schritt Q.0b: PATCH `deals.object_type` (MFH/ETW) aus `objekt.objekttyp.wert` für die ImmoCRM-Spalte "Objekt", läuft immer + idempotent, autoritativ über Modul-0-Insert; v3.6, 2026-05-27 — Sub-Plan 6 ImmoCRM Schritt Q CRM-Sync Q.1–Q.4 inkl. Re-Lauf-Erfolgs-Notiz; v3.5 2026-05-27 Sub-Plan 6 Pflicht-Check Schritt P + Hard-Fail-Entschärfung; v3.4 2026-05-27 Energie + Mietpotenzial neu kalibriert; v3.3 2026-05-26 Stadtteil-Vergleich 5. Achse + Immometrica-Scraper-Härtung). **Workflow-Übersicht:** Schritte 0–8 Datenfindung + Recherche + Scoring; Schritt 8.5 (P) Pflicht-Check Energie/Mieten/Wohnfläche → `state.json.modul_1.pflicht_check`; Schritt 9 State-Write; Schritt 9.5 (Q) CRM-Sync im Akquise-Modus (Q.0 PATCH `deals.markt_pro_m2` aus `eur_per_qm.median` für die "% Markt"-Spalte — läuft immer, idempotent; Q.0b PATCH `deals.object_type` (MFH/ETW) aus `objekt.objekttyp.wert` für die "Objekt"-Spalte — läuft immer, idempotent; Q.1 PATCH `deals.status='offen'` bei Lücke, Q.2 `makler-mail`-Skill-Aufruf non-interactive für Mailto-URL, Q.3 idempotenter `deal_notes`-Insert mit `kind=system_unterlagen_anfrage` + `metadata.mailto_url`, Q.4 Re-Lauf-Erkennung → `system_vollstaendig`-Erfolgs-Notiz wenn vorhin Mangel-Notiz existierte); Schritt 10 Output-Block; Schritt 11 Akquise-Spezialitäten. **Wichtig (seit v3.5):** Modul 1 bricht NICHT mehr bei fehlenden Pflicht-Dateien hart ab — Schritt P schreibt Lücken in den State, Schritt Q übernimmt CRM-Reaktion. Liest Exposé + Mieterliste + Energieausweis + Modernisierungsliste + E-Mail-Body holistisch, extrahiert in objektdaten.json (vollständig annotiert), ruft Recherche-Pipeline (BORIS + 4 Portale mit 6 Immometrica-Configs + Notion-GMB Lage-Klassen + Mietspiegel), berechnet 6-dim Lage-Sub-Score (inkl. GMB) + 5-Sub-Score-Overview + Schnellkennzahlen (Mietmultiplikator, Brutto-Rendite, NRW-KNK 12 %, Aufteilungs-Spread Faktor 14) + Cashflow (80 % Beleihung, 6 % Annuität, Ist/Soll-Rendite EK). Vollautomatisch, keine User-Fragen. Wird vom Orchestrator (`aufteiler`) aufgerufen, vom Modul 0 (`aufteiler-modul-0-akquise-automatisierung`) am Ende einer Mail-Pipeline-Verarbeitung, oder manuell auf einen bereits aufgeräumten Lead-Ordner zeigend.
---

# Modul 0 — Datenbasis (v2.1)

**Vollautomatischer Daten-Extraktor + Markt-Recherche + Scoring.**

Lies das Schema-Dokument zuerst: `docs/objektdaten-schema.md`. Das ist die verbindliche Strukturvorlage für `objektdaten.json`.

**Kernprinzipien:**
1. Holistische Extraktion aus allen Pflicht-Quellen (Opus 4.7 Max-Reasoning)
2. **Vollerfassung mit Anti-Verlust:** Schema ist KEINE Whitelist. Jeder relevante Fakt landet entweder in einem strukturierten Block ODER in `freitext_befunde[]`. **Lieber zu viel als zu wenig.**
3. Hard fail bei nicht-extrahierbaren Pflicht-Feldern (kein Raten, keine User-Frage, keine Defaults für Pflicht)
4. Excel-Kompatibilität (siehe Schema-Doku → Excel-Mapping-Spalten)
5. Keine Sub-Skill-internen Status-Ankündigungen — Skill macht, am Ende Output
6. **Pflicht-Self-Check (Second Pass):** Nach Extraktion alle Quellen nochmal durchsehen mit der Frage *"Was habe ich übersehen?"*. Coverage-Check dokumentieren.

## 0. Modus-Erkennung

| Indikator | Modus |
|---|---|
| User-Prompt enthält "im Akquise-Modus" + Ordnerpfad | `akquise` |
| Ordnerpfad zeigt auf `_inbox/<msg-id>/` mit `_meta.json` + `.processing` | `akquise` |
| Aufruf vom Orchestrator mit `objekt_slug` ODER bestehender `runs/<slug>/` | `orchestrator` |

Modus beeinflusst nur die **Output-Targets** (Akquise: Supabase-Inserts + Ordner-Rename; Orchestrator: nur State-Write). Die **Extraktions-/Recherche-/Scoring-Logik ist identisch**.

## 1. Eingabe-Validierung

### 1.1 Bei `orchestrator`-Modus
- `objekt_slug` vom Orchestrator
- Pfad: `runs/<objekt_slug>/eingangs-daten/` für PDFs
- State: `runs/<objekt_slug>/state.json` (wird in Schritt 12 angelegt/erweitert)

### 1.2 Bei `akquise`-Modus
- `<folder>` aus User-Prompt (alles nach "Ordnerpfad:")
- `_meta.json` lesen (subject, from, files-Liste)
- Duplikat-Check via MD5 (übernommen aus altem Akquise-Modus A.5, siehe Abschnitt 11)

### 1.3 Datei-Klassifikation

Scanne den Ordner. Klassifiziere jede Datei:

| Klasse | Kriterium | Aktion |
|---|---|---|
| `expose` | Dateiname enthält `expose`/`exposé`/`object`/`web-expose` ODER erste Seite hat Maklerlogo + Objekttitel | **LESEN (Liste A)** |
| `mieterliste` | Dateiname enthält `mieter`/`miet-`/`mietaufstellung` ODER Excel mit Spalten `WE`+`Miete`+`m²` | **LESEN (Liste A)** |
| `energieausweis` | Dateiname enthält `energie`/`enev`/`ausweis` ODER Seite 1 trägt Überschrift "Energieausweis für Wohngebäude" | **LESEN (Liste A)** |
| `modernisierung` | Dateiname enthält `modern`/`sanierung`/`renovation` ODER tabellarische Gewerk-Auflistung | **LESEN (Liste A)** |
| `email_body` | Datei = `body.txt` | **LESEN (Liste A)** |
| `irrelevant` | Grundbuch / Flurkarte / Baulastenverzeichnis / Teilungserklärung / Hausgeld / Wartung / Versicherung / sonstige Anhänge | **IGNORIEREN (Liste B)** — nur Dateiname in `quellen.weitere_quellen[]` notieren |

Bei Unklarheit (z.B. `Anlage_3.pdf`): erste Seite lesen, dann Klasse zuordnen. Wenn keine der ersten 5 Klassen passt → `irrelevant`.

### 1.4 Pflicht-Daten-Markierung (Sub-Plan 6 ImmoCRM, seit 2026-05-27 — kein Hard-Fail mehr)

**Bisher (vor Sub-Plan 6):** Modul 1 brach hart ab, wenn Exposé oder Mieterliste fehlten.

**Neu:** Lead darf trotz fehlender Pflicht-Dateien durchlaufen. Der eigentliche
Pflicht-Check passiert am Ende auf den **extrahierten Objektdaten** (Schritt 8.5 / P)
— nicht auf den Dateinamen. Dort wird `state.json.modul_1.pflicht_check` mit
`status` (`vollstaendig` | `unvollstaendig`) und `fehlend[]` (Werte aus
`energie`, `mieten`, `wohnflaeche`) geschrieben. Modul 1 läuft IMMER bis zum
State-Write durch — Owner sieht den Lead im CRM und bekommt eine System-Notiz
mit Unterlagen-Anfrage, falls etwas fehlt.

**Was hier weiterhin gemacht wird:**

1. Optional `_meta.json` (Akquise-Modus, `<lead>/.aufteiler/_meta.json` nach
   Modul-0-Verarbeitung oder `<inbox>/_meta.json` vor Modul-0-Move) lesen.
   Wenn vorhanden + `daten_check_modul_0`-Block gesetzt: Marker als
   Plausibilitäts-Vorinfo notieren in `meta.warnungen[]`, z.B.
   `"Modul 0 meldete: mieten_dokument_vorhanden=false"`. Kein Abbruch.
2. Datei-Klassifikation aus Schritt 1.3 weiter benutzen — die fehlenden
   Klassen werden in der späteren Extraktion (Schritt 3) als "nicht
   extrahierbar" auftauchen und sich in den Konfidenz-Markern niederschlagen.
3. **Modernisierungs-Info** ist nicht mehr Teil des Hard-Checks — fehlt sie
   ganz (weder Datei noch Exposé-Block), wird `modernisierung_bestand` mit
   leeren Slots befüllt (alle 8 Gewerke `jahr=null`), und der Zustand-Sub-Score
   wird entsprechend niedrig — kein Abbruch.

**Wann bricht Modul 1 trotzdem hart ab?** Nur noch in folgenden Fällen:

| Fall | Begründung |
|---|---|
| `<folder>` existiert nicht / nicht lesbar | Skill kann nicht arbeiten |
| Keine **einzige** lesbare Datei im Ordner (auch kein body.txt) | Keine Datenquelle |
| Adresse kann nicht extrahiert werden (`adresse.strasse.wert = null`) UND `<folder>`-Slug ist Adress-Fallback `unbekannt - <msg-id-short>` | Lead hat keine Adresse → kein sinnvoller Markt-Lookup. Lead wird mit `pflicht_check.status=unvollstaendig` und `fehlend=["adresse", ...]` als manuell-zu-bearbeiten markiert (state.json wird trotzdem geschrieben, Modul 0 setzt `priority_score=null`). |

Alle anderen früheren Hard-Fail-Gründe (fehlende Mieterliste, fehlender
Energieausweis, fehlende Modernisierungsliste) sind **keine Abbruch-Gründe
mehr**. Modul 1 läuft durch, schreibt `pflicht_check` und überlässt dem
CRM-Frontend (System-Notiz + `deals.status='offen'`) das Owner-Signal.

**Status-Konsistenz (2026-06-03):** Wenn Modul 1 hier wirklich hart abbricht
(kein `state.json` geschrieben — Hard-Fail oben oder Crash), übernimmt **Modul 0
die Status-Korrektur** in seiner Fehler-Behandlung (Schritt L): `deals.status='offen'`
mit `priority_score=null`. Ein Lead mit `status='pre_screened'` + `priority_score=null`
darf nach Abschluss eines Laufs NIE bestehen bleiben — er gehört nach „Offen"
(manueller Handlungsbedarf), nicht in „Auto-Analyse". Zusätzliches Sicherheitsnetz
im CRM-Backend: der `pull`-Endpoint reaped solche Analyse-Leichen (>30 Min alt)
nach `offen`, falls ein Crash sogar die Modul-0-Fehlerbehandlung übersprungen hat.

## 2. Liste-A in Kontext laden

Alle Liste-A-Files **gleichzeitig** in den Kontext lesen:
- PDFs: `Read`-Tool (mit `pages`-Parameter für >10 Seiten)
- XLSX: Falls Mieterliste Excel ist, mit `python tools/read_xlsx.py <path>` (falls Tool existiert) oder `Read` (Python-Helper schreibt JSON-Repräsentation auf stdout)
- `body.txt`: `Read`-Tool

**Wichtig:** Holistisch arbeiten — alle Dokumente liegen parallel vor, nicht sequenziell extrahieren.

## 3. Holistische Datenextraktion (Opus 4.7 Max-Reasoning)

Extrahiere in `objektdaten.json` gemäß Schema `docs/objektdaten-schema.md`. **Vollerfassung — je mehr Felder, desto besser.**

### 3.1 Regeln pro Feld

- Jeder Wert mit `wert`/`quelle`/`zitat`/`konfidenz`
- `quelle`-Format: `<dateiname>:<seite|section>:<column-or-cell>`, z.B. `"Mieterliste.xlsx:Zeile 5 Spalte D"` oder `"Expose.pdf:S.3"`
- `zitat`: exakter Wortlaut max 200 Zeichen
- `konfidenz`:
  - `hoch`: wörtlich, eindeutig
  - `mittel`: aus Kontext abgeleitet ODER nur eine Quelle ohne Cross-Reference
  - `niedrig`: Diskrepanz oder reine Annahme

### 3.2 Cross-Reference aktiv suchen

Suche bewusst nach Überschneidungen:
- Baujahr in Exposé + Energieausweis → wenn übereinstimmend: `quelle = "Expose.pdf:S.3 || Energieausweis.pdf:S.1"`, `konfidenz = hoch`
- Heizungs-Bj in Exposé + Energieausweis → idem
- Wohnfläche-Summe in Exposé + Σ Mieterliste → idem
- WE-Anzahl in Exposé-Text + Anzahl Mieterliste-Zeilen → idem

### 3.3 Diskrepanz-Behandlung

Wenn zwei Quellen widersprechen:

**Bei nicht-kritischen Feldern:**
- `wert` = der wahrscheinlichere (z.B. spezifischere Quelle)
- `konfidenz` = `niedrig`
- `quelle` = `"DISKREPANZ: Quelle A sagt X, Quelle B sagt Y, gewählt X weil..."`
- `meta.warnungen[]` ergänzen

**Bei kritischen Feldern** (`adresse`, `objekt.baujahr`, `objekt.anzahl_we`, `preise.angebotspreis_eur`):
- **HARTER STOPP**:
```
Modul 0: Diskrepanz im kritischen Feld <pfad>:
  Quelle A (<file>): <wert_a> ("<zitat_a>")
  Quelle B (<file>): <wert_b> ("<zitat_b>")
Bitte Material prüfen und korrigieren.
```

### 3.4 WE-Liste — Ground Truth ist die Mieterliste

- Anzahl Zeilen in Mieterliste = `objekt.anzahl_we.wert`
- Pro WE alle Felder aus Mieterliste-Spalten extrahieren
- Wenn Mieterliste-Spalte leer / Mietername fehlt → `leer.wert = true`
- `ist_miete_eur_pro_qm` immer berechnen (`ist_miete_eur_monat / wohnflaeche_qm`)
- Reihenfolge in `we_liste[]` = Reihenfolge in Mieterliste (für Excel-Mapping `8+i`)

### 3.5 Modernisierungs-Bestand

8 Gewerke gemäß ImmoWertV (siehe Schema):
- dach, fassade, fenster, leitungen, heizung, baeder, innenausbau, grundriss

Jedes Gewerk **muss** als Feld vorhanden sein. Wenn keine Sanierung erwähnt → `jahr=null, art=null, konfidenz=hoch` ("R02 — fehlt = keine Sanierung").

Quellen: dedizierte Modernisierungsliste (falls vorhanden) hat Vorrang. Sonst aus Exposé-Fließtext extrahieren ("Dach 2018 neu", "neue Fenster 2005", etc.).

### 3.6 Energieausweis

Wenn vorhanden: Klasse, Kennwert, Energieträger, Heizungsart-Detail, Ausstellungsdatum, Gültig-bis extrahieren.
Wenn nicht vorhanden: Block ganz weglassen ODER `klasse.wert = "unbekannt"`, `konfidenz = niedrig`.

### 3.7 Catch-All — `freitext_befunde[]` (Anti-Verlust)

**Pflicht-Schritt:** Während der Extraktion sammelst du parallel alle Fakten die KEIN passendes Schema-Feld haben aber für die Objekt-Bewertung relevant sind.

**Beispiele was hier reinkommt:**
- Lage-Spezifika ohne Schema-Slot (Bahnnähe, Lärmschutz nachgerüstet, Fluglärm, Hochwassergebiet)
- Mietverhältnis-Besonderheiten (sehr lange Mietdauer einzelner WE, Sondervereinbarungen, gekündigte Mieter)
- Geplante aber nicht beauftragte Sanierungen
- Hausgemeinschafts-Themen (Hausmeister im Haus, Konflikte, Pflicht-Mitgliedschaften)
- Verkaufsmotiv falls genannt (Erbe, Trennung, Insolvenz)
- Besondere Ausstattung einzelner WE (Loggia nur bei einer WE, Sauna im Keller)
- Pflichten aus GEG/EnEV die in den nächsten Jahren greifen
- Erbbaurecht-Details, Wegerecht, sonstige Lasten erwähnt im Exposé
- Spezielle Mieter-Demografie wenn erwähnt
- **Alles** was du beim Lesen denkst "das könnte für die Bewertung relevant sein und passt nicht ins Schema"

**Pro Eintrag:** `thema`, `befund`, `quelle`, `zitat`, `relevanz` (hoch/mittel/niedrig), optional `wirkung_auf_score`.

**Anti-Pattern:** KEINE Schema-Felder duplizieren. Wenn Baujahr im Freitext steht, gehört es in `objekt.baujahr`, NICHT in `freitext_befunde[]`.

### 3.8 SECOND PASS — Self-Check Vollerfassung (Pflicht)

**Nach** der ersten Extraktion (Schritte 3.1–3.7) liest das LLM die Pflicht-Quellen **ein zweites Mal** durch mit dem Fokus:

> *"Welche Fakten stehen in den Quellen, die ich in der ersten Runde noch nicht in `objektdaten.json` notiert habe?"*

Konkrete Fragen:
- Habe ich alle Mieterliste-Spalten erfasst? Auch Sondernotizen, Anmerkungen, Fußnoten?
- Habe ich alle Exposé-Seiten durchgegangen? Auch Anhänge, Bildunterschriften, Tabellen?
- Steht im Energieausweis etwas zu Pflicht-Sanierungen, Empfehlungen, geplanten Maßnahmen?
- Erwähnt der Mail-Body zusätzliche Infos die nicht im Exposé stehen?

**Gefundene Befunde** werden ergänzt in entweder strukturiertem Block (wenn Schema-Slot existiert) oder `freitext_befunde[]` (wenn nicht).

**Dokumentation des Second-Pass** in `meta.coverage_check`:
```json
"coverage_check": {
  "expose_seiten_gelesen": 12,
  "mieterliste_zeilen_gelesen": 11,
  "energieausweis_seiten_gelesen": 4,
  "anzahl_strukturierte_felder": 87,
  "anzahl_freitext_befunde": 6,
  "stichproben_zitate": [
    { "zitat": "Dach wurde 2018 komplett neu eingedeckt mit Aufdach-Dämmung", "quelle": "Expose.pdf:S.4", "extrahiert_nach": "modernisierung_bestand.dach" },
    { "zitat": "WE 7 vermietet an Herrn Müller seit April 1985", "quelle": "Mieterliste.xlsx:Zeile 8 H", "extrahiert_nach": "we_liste[6].mieter_seit + freitext_befunde[1]" },
    { "zitat": "Aufgrund Bahnlinie Schallschutzfenster eingebaut", "quelle": "Expose.pdf:S.4", "extrahiert_nach": "freitext_befunde[0]" },
    ...
  ],
  "second_pass_durchgeführt": true
}
```

**Minimum 5 Stichproben-Zitate**, die einen Querschnitt durch die Quellen zeigen.

**Wenn `freitext_befunde[]` leer bleibt nach Second-Pass:** Pflicht-Begründung in `meta.coverage_check.no_freitext_befunde_begruendung`, z.B. *"Exposé enthält ausschließlich Standard-Felder die alle in strukturierten Blöcken extrahiert wurden"*. Leeres Array ohne Begründung ist ein Validator-Fehler.

## 4. Pflicht-Feld-Markierung (Sub-Plan 6 ImmoCRM, seit 2026-05-27 — kein Hard-Fail mehr außer Adresse)

**Bisher (vor Sub-Plan 6):** Hard-Fail bei jedem fehlenden Pflicht-Feld.

**Neu:** Pflicht-Felder werden weiterhin geprüft, aber die Lücken landen in
`meta.daten_check.fehlend` (für Audit) und werden dann in Schritt 8.5 (Pflicht-
Check / P) zu `state.json.modul_1.pflicht_check.fehlend` aggregiert. Modul 1
bricht **nicht** ab — der Lead taucht im CRM mit Status `offen` + Unterlagen-
Anfrage-Notiz auf.

**Was hier passiert:**

1. Pflicht-Feld-Liste aus dem Schema durchgehen (siehe Schema-Doku Abschnitt
   "Pflicht-Felder").
2. Pro fehlendem Pflicht-Feld einen Eintrag in `meta.daten_check.fehlend[]`
   schreiben, NICHT abbrechen.
3. Falls `modernisierung_bestand` komplett leer (kein einziger Gewerk-Block,
   auch nicht mit `jahr=null`): wie bisher die 8 Gewerk-Slots mit `jahr=null,
   art=null, konfidenz=hoch` befüllen ("R02 — fehlt = keine Sanierung")
   und einen Hinweis in `meta.warnungen[]` setzen. Kein Abbruch.

**Einziger weiterhin geltender Hard-Fail (siehe Schritt 1.4 Tabelle):**

- Adresse fehlt **UND** `<folder>`-Slug ist `unbekannt - <msg-id-short>` →
  Skill schreibt state.json mit `modul_1.pflicht_check.status="unvollstaendig"`,
  `fehlend=["adresse"]` plus etwaige andere Lücken, und beendet sich mit
  Exit-Code 0 (kein Fehler — der Lead ist legitim "manuell zu prüfen").
  Modul 0 setzt anschließend `priority_score=null` in Supabase.

## 5. Recherche-Tools (parallel)

Alle drei parallel starten — `Bash` mit `run_in_background=true` für die Scraper, dann sammeln.

### 5.1 BORIS-Lookup (BRW)

```bash
python tools/m01_boris_brw.py \
  --strasse "<adresse.strasse.wert>" \
  --hausnr "<adresse.hausnummer.wert>" \
  --plz "<adresse.plz.wert>" \
  --ort "<adresse.ort.wert>"
```

**Keine Adress-Bestätigung** (anders als im alten Modul 1) — die Adresse ist hier aus dem Exposé extrahiert, also bereits validiert durch die LLM-Extraktion. Bei exit 0 direkt übernehmen.

- exit 0: `markt.boris.brw_eur_pro_qm = <wert>`, alle Metadaten füllen, `quelle_status = "ok"`
- exit 1: `brw_eur_pro_qm = null`, `quelle_status = "error: <msg>"`, `meta.warnungen[]` ergänzen
- exit 2 (Adress-mehrdeutig): `quelle_status = "manuell_erforderlich"`, in Folge-Modul-1 manuell setzen

### 5.2 Portal-Pipeline (4 Portale)

```bash
cd c:/meine-projekte/Immobilien/Aufteiler/tools/portal-bewertung
.venv/Scripts/python.exe m00_portal_pricer.py --alle \
  --strasse "..." --hausnr "..." --plz "..." --ort "..." \
  --baujahr <objekt.baujahr.wert> \
  --zustand <ausstattung.zustand_innen.wert oder "normal"> \
  --ausstattung <ausstattung.gesamteindruck.wert oder "normal"> \
  --anzahl-we <objekt.anzahl_we.wert> \
  --wohnflaechen-qm "<komma-separiert aus we_liste>" \
  --zimmer-liste "<komma-separiert>" \
  --badezimmer-liste "<komma-separiert>" \
  --anzahl-garagen <objekt.anzahl_garagen.wert oder 0> \
  --anzahl-aussenstellplaetze <objekt.anzahl_aussenstellplaetze.wert oder 0> \
  --headless
```

Output-JSON parsen:
- `markt.portale.{check24,homeday,interhyp,immometrica}` → vollständig befüllen
- `markt.konsens.median_eur` = Konsens-Median über erfolgreiche Portale
- `markt.konsens.spread_prozent` = relativer Spread
- `markt.konsens.anzahl_quellen` = `n` von 4
- `markt.konsens.quelle_status` = `"<n> von 4"` oder `"fehler"` wenn 0

**Immometrica liefert 6 Configs:** Verkauf-PLZ, Verkauf-Stadt, Miete-PLZ, Miete-Stadt, MFH-PLZ, MFH-Stadt. Jede Config zusätzlich mit dimensionalen Sub-Charts (pro Zimmerklasse, pro Wohnfläche, pro Baujahresgruppe). Schreibe in `markt.portale.immometrica` gemäß Schema v2.1 (siehe `docs/objektdaten-schema.md` Block `markt.portale.immometrica`):

> **Status-Gate pro Config (Pflicht, seit v3.8).** Übernimm Werte NUR aus Configs mit
> `extra.<slot>.status == "ok"`. Die Status-Werte `geo_mismatch`, `geo_not_set` und
> `stale_heading` bedeuten: der Adapter hat die Zahlen verworfen, weil Ort-Filter oder
> Stat-Seite nicht zur Config passten — behandle den Slot dann als **fehlend** (`null`),
> niemals als Wert. Grund: ohne gesetzten Ort-Filter liefert Immometrica bundesweite
> Zahlen, die optisch plausibel aussehen (Ausfall 2026-09-10: 41284 Angebote / 3341 €/m²
> als PLZ-Wert für 45355 Essen statt 12 / 2151). Diagnose-Felder pro Config:
> `geo_check.{expected,actual,match}` und `heading_check.{expected,actual,match}`.

```
markt.portale.immometrica.etw_verkauf.plz   = { median_eur_pro_qm, vermarktungsdauer_tage, inserate_anzahl, stand }
markt.portale.immometrica.etw_verkauf.stadt = { ... }
markt.portale.immometrica.etw_verkauf.ratios = {
  eur_pro_qm_premium_prozent      = (plz.median / stadt.median - 1) * 100,
  vermarktungsdauer_ratio_prozent = (plz.tage   / stadt.tage   - 1) * 100,
  inserate_anzahl_plz_anteil_prozent = plz.inserate / stadt.inserate * 100
}
markt.portale.immometrica.etw_verkauf.dimensionale_sub_charts.plz   = { pro_zimmerklasse, pro_wohnflaeche, pro_baujahresgruppe }
markt.portale.immometrica.etw_verkauf.dimensionale_sub_charts.stadt = { ... }

markt.portale.immometrica.miete.plz       = { median_eur_pro_qm_monat, vermarktungsdauer_tage, inserate_anzahl, stand }
markt.portale.immometrica.miete.stadt     = { ... }
markt.portale.immometrica.miete.ratios    = analog etw_verkauf
markt.portale.immometrica.miete.dimensionale_sub_charts = analog

markt.portale.immometrica.mfh.plz         = { median_eur_pro_qm, inserate_anzahl, stand }
markt.portale.immometrica.mfh.stadt       = { ... }
markt.portale.immometrica.mfh_gap = {
  eur_pro_qm_etw_plz = etw_verkauf.plz.median_eur_pro_qm,
  eur_pro_qm_mfh_plz = mfh.plz.median_eur_pro_qm,
  gap_prozent        = (mfh - etw) / etw * 100
}
```

**Backwards-Compat-Aliase parallel schreiben** (für Excel-Mapping `KALKU!I14` + Folge-Module die alte Felder lesen):

```
markt.portale.immometrica.eur_pro_qm                     = etw_verkauf.plz.median_eur_pro_qm
markt.portale.immometrica.plz_median_eur_pro_qm          = etw_verkauf.plz.median_eur_pro_qm
markt.portale.immometrica.stadt_median_eur_pro_qm        = etw_verkauf.stadt.median_eur_pro_qm
markt.portale.immometrica.vermarktungsdauer_median_tage  = etw_verkauf.plz.vermarktungsdauer_tage
markt.portale.immometrica.inserate_anzahl_plz            = etw_verkauf.plz.inserate_anzahl
markt.portale.immometrica.plz_premium_prozent            = etw_verkauf.ratios.eur_pro_qm_premium_prozent
```

### 5.3 Notion-Lookups

**GMB (Grundstücksmarktbericht) — strukturiert lesen (seit v2.1):**

- Notion-DB Page-ID `3310ae59-38e4-81f1-ad36-e8bd809d437a` ("Preisdatenbank GMB")
- Query nach `adresse.ort.wert` → Stadt-Page (Essen / Dortmund / Bochum / Herne / Hagen / Iserlohn / Kreis Unna)
- Page-Content parsen:
  - **Lage-Klassen-Tabelle** (3 Klassen × {Median, Min, Max}):
    ```
    markt.gmb.lage_klassen.gut     = { eur_pro_qm, spanne_eur_pro_qm: { min, max } }
    markt.gmb.lage_klassen.mittel  = { eur_pro_qm, spanne_eur_pro_qm: { min, max } }
    markt.gmb.lage_klassen.maessig = { eur_pro_qm, spanne_eur_pro_qm: { min, max } }
    ```
  - **Marktdruck-Tabelle** (% angespannt Miete + Eigentum):
    ```
    markt.gmb.marktdruck = { prozent_angespannt_miete, prozent_angespannt_eigentum, stand }
    ```
  - **BRW-Spanne MFH** (falls auf der Page):
    ```
    markt.gmb.brw_spanne_mfh = { min_eur_pro_qm, max_eur_pro_qm, stand }
    ```
- **Objekt-Einschätzung** (auto):
  - `konsens_median = markt.konsens.median_eur / objekt.wohnflaeche_gesamt_qm`
  - Vergleich mit den 3 Lage-Klassen-Medians → Klasse mit niedrigstem Abstand
  - Schreibe `markt.gmb.objekt_einschaetzung = { klasse, konsens_median_eur_pro_qm, begruendung_kurz }`
- **Backwards-Compat-Alias** für `KALKU!I17`:
  ```
  markt.gmb.eur_pro_qm = markt.gmb.objekt_einschaetzung.konsens_median_eur_pro_qm
  ```
- Kein Stadt-Page-Treffer: alle GMB-Felder = null, `markt.gmb.objekt_einschaetzung.klasse = null`, `meta.warnungen[]` ergänzen.

**Mietspiegel NRW:**
- Notion-DB Page-ID `8b000923-d5ee-45a4-8f6a-e7f3bf81f20e` ("Mietspiegel NRW")
- Query nach `adresse.ort.wert`
- Treffer: Mietspiegel-Block befüllen:
  - `basis_eur_pro_qm`
  - `baujahres_klasse` (aus `objekt.baujahr.wert` ableiten)
  - `lage_korrektur_eur_pro_qm` (Default: 0, sofern Lage-Detail nicht ableitbar)
  - `obergrenze_eur_pro_qm` (üblich +18% auf Basis-Wert)
  - `kappungsgrenze_prozent`: 0.15 (NRW-Default)
  - `mietpreisbremse`: bool aus Notion oder false
- Kein Treffer: `mietspiegel` mit nulls, `meta.warnungen[]` ergänzen

### 5.4 Eckdaten-Rechnung (seit v2.1)

Nach Portal-Pipeline + Mietspiegel-Lookup. Schreibe in `markt.eckdaten`:

**Soll-Kaltmiete (Jahres-Σ):**

```python
soll_pro_qm = markt.mietspiegel.basis_eur_pro_qm or markt.portale.immometrica.miete.plz.median_eur_pro_qm_monat
jahres_soll_kaltmiete = sum(we.wohnflaeche_qm.wert for we in we_liste) * soll_pro_qm * 12
```

Wenn beide Quellen fehlen → ANNAHME-Marker in `meta.daten_check.annahmen[]` setzen mit Konfidenz `niedrig`, Cashflow-Block überspringen.

**Coach-KPIs:**

```python
mietmultiplikator                = kaufpreis / jahres_soll_kaltmiete
brutto_mietrendite_prozent       = jahres_soll_kaltmiete / kaufpreis * 100
kaufpreis_pro_qm                 = kaufpreis / gesamt_wohnflaeche
kp_vs_immometrica_plz_prozent    = (kaufpreis_pro_qm / etw_verkauf.plz.median_eur_pro_qm - 1) * 100
kp_vs_gmb_mittel_prozent         = (kaufpreis_pro_qm / gmb.lage_klassen.mittel.eur_pro_qm - 1) * 100 or null

kaufnebenkosten_prozent          = 12.0   # NRW-Konstante
kaufnebenkosten_eur              = kaufpreis * 0.12
gesamtinvest_eur                 = kaufpreis + kaufnebenkosten_eur

aufteilungsfaktor                = 14     # Coach-Konstante
ziel_aufteilungserloes_eur       = jahres_soll_kaltmiete * 14
aufteilungs_spread_prozent       = (ziel_aufteilungserloes_eur - gesamtinvest_eur) / gesamtinvest_eur * 100
```

### 5.5 Cashflow-Rechnung (seit v2.1)

Schreibe in `markt.cashflow`:

**Annahmen (User-Konstanten, dokumentiert in Schema):**

```python
beleihungsauslauf_prozent             = 80.0
annuitaet_prozent                     = 6.0   # Zins + Tilgung kombiniert
bewirtschaftungskosten_anteil_prozent = 20.0  # nicht umlagefähige BWK + Mietausfallwagnis + Instandhaltung
```

**Kapital + Annuität:**

```python
beleihungspotenzial_eur = kaufpreis * 0.80
eigenkapital_eur        = gesamtinvest_eur - beleihungspotenzial_eur  # KNK aus EK
jahres_annuitaet_eur    = beleihungspotenzial_eur * 0.06
```

**Ist-Cashflow (aus Bestandsmieten):**

```python
jahres_ist_kaltmiete = sum(we.ist_miete_eur_monat.wert for we in we_liste if not we.leer.wert) * 12
# Wenn alle WE leer ODER ist_miete-Spalte fehlt komplett:
#   ANNAHME: jahres_ist_kaltmiete = jahres_soll_kaltmiete, in meta.daten_check.annahmen[] notieren

ist.jahres_bwk_eur                  = jahres_ist_kaltmiete * 0.20
ist.cashflow_vor_steuer_eur         = jahres_ist_kaltmiete - ist.jahres_bwk_eur - jahres_annuitaet_eur
ist.cashflow_rendite_auf_ek_prozent = ist.cashflow_vor_steuer_eur / eigenkapital_eur * 100
```

**Soll-Cashflow (Mietspiegel-Median):**

```python
soll.jahres_kaltmiete_eur            = jahres_soll_kaltmiete
soll.jahres_bwk_eur                  = soll.jahres_kaltmiete_eur * 0.20
soll.cashflow_vor_steuer_eur         = soll.jahres_kaltmiete_eur - soll.jahres_bwk_eur - jahres_annuitaet_eur
soll.cashflow_rendite_auf_ek_prozent = soll.cashflow_vor_steuer_eur / eigenkapital_eur * 100

mietsteigerungspotenzial_prozent     = (soll.jahres_kaltmiete_eur - jahres_ist_kaltmiete) / jahres_ist_kaltmiete * 100
```

**Hinweis:** Tilgungs-Restschuld-Projektion über N Jahre macht Modul 0 **nicht** — das ist Modul 5 / PDF-Export.

### 5.6 Daten-Check-Block

Schreibe in `meta.daten_check`:

```python
vorhanden = [<liste der erfolgreich befüllten Pfade>]
fehlend   = [<liste der optionalen Pfade die offen blieben>]   # Pflicht-Felder erzeugen Hard-Fail, kommen nie hier rein
annahmen  = [
  { feld, wert, quelle: "ANNAHME: <begründung>", konfidenz: "niedrig|mittel|hoch" }
  für jede setzbare Annahme im Lauf (z.B. Ist-Miete fehlt → = Soll)
]
```

### 5.7 PLZ + Stadt-Einwohner-Lookup (Helper, eingeführt v3.2)

**Status (seit v3.2):** Optionaler Helper. Wird vom Modul 1 aktuell **nicht zwingend aufgerufen** — die "Anzeigen pro 1.000 EW / Monat"-Achse, für die der Helper ursprünglich gebaut wurde, wurde nach Sanity-Check verworfen (siehe `docs/anzeigen-pro-ew-sanity-check.md`).

Das Tool bleibt verfügbar für künftige Module die EW-Daten brauchen (z.B. Markt-Tiefe-Berechnungen in Modul 6, oder Cross-Stadt-Vergleiche in einem späteren Skill).

```bash
python tools/plz_einwohner_lookup.py <plz> "<ort>"
```

Output (JSON auf stdout):

```json
{
  "plz_einwohner":   { "wert": <int>, "quelle": "...", "konfidenz": "hoch|mittel|niedrig", "abgerufen_am": "YYYY-MM-DD" },
  "stadt_einwohner": { "wert": <int>, "quelle": "...", "konfidenz": "...", "abgerufen_am": "..." },
  "fehlende_eintraege": []
}
```

Exit-Codes:
- `0`: PLZ + Stadt im Cache, beide Werte geliefert.
- `2`: Cache-Miss — fehlt mindestens einer. Dann WebSearch ausführen ("Einwohner PLZ XXXXX <Ort>" + "Einwohner <Ort> 2026"), `tools/plz-einwohner.csv` ergänzen, Skript erneut aufrufen.

**Quellen-Kaskade für WebSearch-Fallback:**
1. Wikipedia (für Stadt-EW typisch belastbar)
2. onlinestreet.de / suche-postleitzahl.org (für PLZ-EW)
3. Statistische Landesämter (für NRW: kreis-soest.de, it.nrw.de, stadt-koeln.de, etc.)

Konfidenz-Marker setzen:
- `hoch`: amtliche Quelle (Statistisches Landesamt / Stadt) ODER 2 unabhängige Quellen stimmen überein
- `mittel`: nur 1 PLZ-Schätzungs-Quelle (onlinestreet.de etc.)
- `niedrig`: Schätzung aus Stadt-Geographie hochgerechnet

## 6. Marktwert-Konsens + Gap

```
konsens_median  = markt.konsens.median_eur
angebot         = preise.angebotspreis_eur.wert
gap_eur         = angebot - konsens_median
gap_prozent     = (gap_eur / konsens_median) * 100
```

→ in State unter `modul_1.gap_eur`, `modul_1.gap_prozent`, `modul_1.gap_ampel` (`grün` ≤ 0%, `gelb` 0–5%, `rot` > 5%).

## 7. Scoring 0-10 berechnen

Siehe Schema-Doku Abschnitt `scoring`. Konkret:

### 7.1 Sub-Score `lage` — 6-dim Variante B (seit v2.1)

```python
ev  = markt.portale.immometrica.etw_verkauf
mt  = markt.portale.immometrica.miete
gmb = markt.gmb.objekt_einschaetzung

def safe(val, default=5):
    return default if val is None else val

# k1 — Verkaufs-Premium PLZ vs. Stadt
k1 = clamp(0, 10, 5 + safe(ev.ratios.eur_pro_qm_premium_prozent, 0) / 4)

# k2 — Mieten-Premium PLZ vs. Stadt
k2 = clamp(0, 10, 5 + safe(mt.ratios.eur_pro_qm_premium_prozent, 0) / 4)

# k3 — Verkaufs-Liquidität (kürzere Vermarktungsdauer = besser)
k3 = clamp(0, 10, 5 - safe(ev.ratios.vermarktungsdauer_ratio_prozent, 0) / 8)

# k4 — Mieter-Nachfrage (kürzere Vermarktungsdauer Miete = besser)
k4 = clamp(0, 10, 5 - safe(mt.ratios.vermarktungsdauer_ratio_prozent, 0) / 8)

# k5 — Markt-Tiefe (PLZ-Anteil an Stadt-Inseraten)
k5 = clamp(0, 10, ((safe(ev.ratios.inserate_anzahl_plz_anteil_prozent, 30)
                    + safe(mt.ratios.inserate_anzahl_plz_anteil_prozent, 30)) / 2) / 3)

# k6 — GMB-Lage-Klasse
k6 = { "gut": 8, "mittel": 5, "mäßig": 2, None: 5 }.get(gmb.klasse if gmb else None, 5)

w = { "k1": 0.22, "k2": 0.18, "k3": 0.18, "k4": 0.17, "k5": 0.10, "k6": 0.15 }
sub_score_lage = (k1*w["k1"] + k2*w["k2"] + k3*w["k3"] + k4*w["k4"] + k5*w["k5"] + k6*w["k6"])
```

Fehlt eine Komponente komplett (Tool-Fehler) → Komponente = 5 (neutral), Gewicht bleibt.

Ampel: ≥7 grün / 4–7 gelb / <4 rot.

Begründungs-Text: `f"PLZ-ETW {(k1-5)*4:+.0f}% / Miete-PLZ {(k2-5)*4:+.0f}% / GMB-Lage {gmb.klasse or '–'}"`

### 7.2 Sub-Score `miet_potenzial` (v3.4 — Ziel-Kaskade + 50%-Cap)

```python
ist_schnitt = sum(we.ist_miete_eur_monat.wert for we in we_liste if not we.leer.wert) / \
              sum(we.wohnflaeche_qm.wert  for we in we_liste if not we.leer.wert)

# Ziel-Kaskade: Mietspiegel-Obergrenze (§558-Maximum, legaler Hebel auf Bestandsmieter)
# hat Priorität — Fallback Markt-Median PLZ (Immometrica) bei Mietspiegel-DB-Lücke.
obergrenze    = markt.mietspiegel.obergrenze_eur_pro_qm
markt_median  = markt.portale.immometrica.miete.plz.median_eur_pro_qm_monat

if obergrenze is not None:
    ziel        = obergrenze
    ziel_quelle = "mietspiegel_obergrenze"
elif markt_median is not None:
    ziel        = markt_median
    ziel_quelle = "immometrica_miete_plz_median"
else:
    ziel        = None
    ziel_quelle = None

if ziel and ist_schnitt > 0:
    potenzial_prozent = (ziel / ist_schnitt - 1) * 100
    # Progressive Skalierung — 50 % Hebel → volle 10 Punkte (Cap).
    # 10 % → 2 P · 25 % → 5 P · 40 % → 8 P · 50 %+ → 10 P.
    # Begründung: 50 % Hebepotenzial ist bei Bestandsobjekten bereits ein
    # außergewöhnlicher Aufteiler-Deal; höhere Werte sind meist Rechen-Artefakte
    # (extrem niedrige Alt-Mieten) und sollen nicht überschätzt werden.
    sub_score_miete = max(0, min(10, potenzial_prozent / 5))
else:
    sub_score_miete   = 5   # neutral — kein Markt-Bezug verfügbar
    potenzial_prozent = None
```

State-Felder zur Nachvollziehbarkeit:
- `scoring.miet_potenzial.ziel_eur_pro_qm`        = `ziel`
- `scoring.miet_potenzial.ziel_quelle`            = `ziel_quelle` (`mietspiegel_obergrenze` | `immometrica_miete_plz_median` | `null`)
- `scoring.miet_potenzial.ist_schnitt_eur_pro_qm` = `ist_schnitt`
- `scoring.miet_potenzial.potenzial_prozent`     = `potenzial_prozent`

Ampel: ≥6 grün / 3–6 gelb / <3 rot.

### 7.3 Sub-Score `energie` (v3.4 — Stützpunkte C=10 / D=9 / H=1, linear interpoliert)

Mapping-Tabelle direkt aus Schema. Drei User-Stützpunkte (C=10, D=9, H=1)
mit linearer Interpolation zwischen D und H (Δ=2 pro Stufe → E=7, F=5, G=3)
und Cap bei 10 für alle Klassen besser als C (A+/A/B liefern keinen
zusätzlichen Bonus gegenüber C — Energiequalität "C oder besser" ist
in NRW-Bestand bereits Top und wird voll belohnt):

```python
energie_map = {
    "A+": 10, "A": 10, "B": 10, "C": 10,   # Cap — C oder besser = voller Score
    "D":  9,                                # User-Stützpunkt
    "E":  7,                                # linear: D-2
    "F":  5,                                # linear: E-2
    "G":  3,                                # linear: F-2
    "H":  1,                                # User-Stützpunkt
    "unbekannt": 5,                         # neutral, kein Energieausweis im Material
}
klasse = energieausweis.klasse.wert if energieausweis else "unbekannt"
sub_score_energie = energie_map.get(klasse, 5)
```

Ampel: ≥7 grün / 4–7 gelb / <4 rot.

### 7.4 Sub-Score `zustand`

```python
mod_count = sum(1 for g in modernisierung_bestand.values() if g.get("jahr"))
mod_score = mod_count / 8 * 10

bonus = 0
zi = ausstattung.zustand_innen.wert if ausstattung else None
if zi == "neuwertig":              bonus = 2
elif zi == "gut":                  bonus = 1
elif zi == "sanierungsbeduerftig": bonus = -2

sub_score_zustand = max(0, min(10, mod_score + bonus))
```

### 7.5 Sub-Score `deal`

```python
sub_score_deal = max(0, min(10, 5 - gap_prozent / 3))
```

### 7.6 Gesamtscore

```python
subscores = [lage, miet_potenzial, energie, zustand, deal]
gesamt = sum(subscores) / len(subscores)

# Penalty
rote_subscores = sum(1 for s in subscores_with_ampel if s.ampel == "rot")
if rote_subscores >= 2:
    gesamt_ampel = "rot"
else:
    gesamt_ampel = "gruen" if gesamt >= 7 else ("gelb" if gesamt >= 5 else "rot")

kurz_fazit = {
    "gruen": "Lohnt sich, Vollanalyse machen",
    "gelb":  "Prüfenswert, kritische Punkte beachten",
    "rot":   "Eher nicht, außer Sondersituation"
}[gesamt_ampel]
```

### 7.7 Stadtteil-Vergleich — 5-Achsen-Markt-Indikator (seit v3.2, 5. Achse seit v3.3)

**Wichtig — was dieser Block ist und was nicht:**

- ✅ Ein **Markt-Vergleichs-Indikator** PLZ vs. Stadt-Aggregat aus Immometrica-Daten (+ MFH-Premium-Achse aus mfh_gap)
- ❌ **KEIN Lage-Urteil** — qualitative Lage-Bewertung (Mietspiegel-Lage-Zuschlag, GMB-Lage-Klasse, Mikrolage) kommt aus anderen Blöcken
- ❌ **KEIN Cross-Stadt-Vergleich** (Soest vs. Düsseldorf etc.) — keine absolute Skala vorhanden

**Fünf Achsen** (eine 6. Achse "Anzeigen pro 1.000 EW / Monat" wurde in v3.2 geprüft und **verworfen** — siehe `docs/anzeigen-pro-ew-sanity-check.md`. Sanity-Check zeigte: Misst tatsächlich Mieter-Fluktuation, nicht Lage-Qualität.)

**Berechnung pro Achse:**

```python
# Achse 1 — Verkaufspreis €/m²
verkauf = {
  "plz":   etw_verkauf.plz.median_eur_pro_qm,
  "stadt": etw_verkauf.stadt.median_eur_pro_qm,
  "delta_prozent": (plz / stadt - 1) * 100,
}

# Achse 2 — Mietpreis €/m²/Mo
miete = analog Achse 1 für etw_miete

# Achse 3 — Vermarktungsdauer Verkauf (Tage)
verm_verkauf = {
  "plz":   etw_verkauf.plz.vermarktungsdauer_tage,
  "stadt": etw_verkauf.stadt.vermarktungsdauer_tage,
  "delta_prozent": (plz / stadt - 1) * 100,
}

# Achse 4 — Vermarktungsdauer Vermietung (Tage)
verm_miete = analog Achse 3 für etw_miete

# Achse 5 — Aufteilungs-Premium PLZ (seit v3.3)
mfh_gap = markt.portale.immometrica.mfh_gap
mfh_plz = markt.portale.immometrica.mfh.plz

# Premium = -gap_prozent  (positive Zahl = ETW teurer als MFH-Paket = Spread)
premium_prozent = -mfh_gap.gap_prozent if mfh_gap else None

# Robustheits-Check gegen Scraper-Quirks (mehrschichtig, eingeführt v3.3):
# Schicht 1 — Scraper-seitig: heading-basierter Diff-Check in
#   `tools/portal-bewertung/portals/immometrica/portal.py::_wait_for_stat_heading`.
#   Bei `status="stale_heading"` werden uebersicht/zusatzinfo auf null gesetzt
#   → mfh.plz ist dann null und unten greift `zu_wenig_inserate`.
# Schicht 2 — Modul-1-Logik (hier): Sanity-Cross-Check auf die Werte selbst.

mfh_plz_value = mfh_plz.median_eur_pro_qm if mfh_plz else None

# Quirk A: MFH-Wert == ETW-Wert (Scraper hat ETW-Werte als MFH gespeichert)
quirk_mfh_eq_etw = (
    mfh_plz_value is not None and
    mfh_plz_value == etw_verkauf.plz.median_eur_pro_qm
)
# Quirk B: MFH-Wert < 200 €/m² (das ist ein Miete-Wert in €/m²/Mo, kein Kaufpreis)
quirk_miete_leck = (mfh_plz_value is not None and mfh_plz_value < 200)
zu_wenig_inserate = (mfh_plz is None) or (mfh_plz.inserate_anzahl < 3)

if quirk_mfh_eq_etw:
    aufteilungs_premium = {"plz": mfh_plz_value, "ampel": "nv",
                            "wort": "Tool-Quirk (MFH=ETW)", "caveat": "tool_quirk_mfh_eq_etw"}
elif quirk_miete_leck:
    aufteilungs_premium = {"plz": mfh_plz_value, "ampel": "nv",
                            "wort": "Tool-Quirk (Miete-Wert geleckt)", "caveat": "tool_quirk_miete_leck"}
elif zu_wenig_inserate:
    aufteilungs_premium = {"plz": mfh_plz_value, "ampel": "nv",
                            "wort": f"zu wenig Inserate ({mfh_plz.inserate_anzahl if mfh_plz else 0})",
                            "caveat": "zu_wenig_inserate"}
else:
    aufteilungs_premium = {"plz": mfh_plz_value, "premium_prozent": premium_prozent,
                            "ampel": "...", "wort": "...", "caveat": None}
```

**Bewertungs-Logik pro Achse (Ampel-Schwellen):**

| Achse | 🟢 grün | 🟡 gelb | 🔴 rot |
|---|---|---|---|
| Verkaufspreis €/m² | Δ ≥ +5 % | ±5 % | Δ ≤ −5 % |
| Mietpreis €/m²/Mo | Δ ≥ +5 % | ±5 % | Δ ≤ −5 % |
| Vermarktung Verkauf | Δ ≤ −20 % | ±20 % | Δ ≥ +20 % |
| Vermarktung Vermietung | Δ ≤ −20 % | ±20 % | Δ ≥ +20 % |
| Aufteilungs-Premium PLZ | ≥ +15 % | +5 % bis +15 % | < +5 % |

**Wort-Einordnung pro Achse (Pflicht, 2–3 Worte, neutral):**

| Achsen-Wert | Wort |
|---|---|
| Preise: Δ ≥ +10 % | "deutliches Premium" |
| Preise: +5 % bis +10 % | "leichtes Premium" |
| Preise: ±5 % | "Stadt-Schnitt" |
| Preise: −5 % bis −10 % | "leicht unter Schnitt" |
| Preise: Δ ≤ −10 % | "deutlich unter Schnitt" |
| Vermarktung: Δ ≤ −50 % | "spürbar schneller" *(nicht "Top-Nachfrage")* |
| Vermarktung: −20 % bis −50 % | "schneller als Stadt" |
| Vermarktung: ±20 % | "Stadt-Schnitt" |
| Vermarktung: ≥ +20 % | "länger online" |
| Aufteilungs-Premium: ≥ +25 % | "starker Aufteilungs-Spread" |
| Aufteilungs-Premium: +15 % bis +25 % | "solider Aufteilungs-Spread" |
| Aufteilungs-Premium: +5 % bis +15 % | "moderater Spread" |
| Aufteilungs-Premium: < +5 % | "kaum Spread (MFH ≈ ETW)" |
| Aufteilungs-Premium: negativ | "kein Spread (MFH > ETW)" |

**Gesamt-Indikator (NICHT "Verdikt"):**

```python
gueltige_achsen = [a for a in 5_achsen if a.ampel != "nv"]  # n/v-Achsen werden geskippt
m = len(gueltige_achsen)
anzahl_gruen = sum(1 for a in gueltige_achsen if a.ampel == "gruen")

# Adaptive Schwellen — Mehrheit grün → grün, knappe Hälfte → gelb, sonst rot
if m == 5:
    indikator = ("gruen", "PLZ über Stadt-Schnitt") if anzahl_gruen >= 4 \
                else ("gelb", "PLZ um Stadt-Schnitt") if anzahl_gruen >= 2 \
                else ("rot", "PLZ unter Stadt-Schnitt")
elif m == 4:  # Achse 5 = n/v
    indikator = ("gruen", "PLZ über Stadt-Schnitt") if anzahl_gruen >= 3 \
                else ("gelb", "PLZ um Stadt-Schnitt") if anzahl_gruen == 2 \
                else ("rot", "PLZ unter Stadt-Schnitt")
else:  # weitere Achsen-Skips (Notfall)
    indikator = ("gelb", "Datenlage zu dünn")  # Disclaimer im Output
```

Im User-Output: "**Indikator:** <Ampel> **<Wort>** — <anzahl_gruen> von <m> Achsen grün"

**Modell-Honesty-Disclaimer (Pflicht im Output):**

Unter der Tabelle in `quickcheck.md`:

> *Hinweis: Markt-Vergleichs-Indikator auf Basis Immometrica-Snapshot H1/<halbjahr> (Baujahr-Filter 1900–1980). **Ersetzt keine qualitative Lage-Bewertung** (Mikrolage, ÖPNV, Lärm, Einkauf, Schulen) — diese kommen aus Mietspiegel-Lage-Zuschlag (Modul 6) und ggf. Notion-GMB-Lage-Klasse. Stichproben: <n_etw>/<m_etw> ETW-Inserate (Verkauf), <n_miete>/<m_miete> Miet-Inserate — Median bei wenigen Inseraten durch Ausreißer beeinflussbar.*

**Stichproben-Warnung** (Pflicht bei < 30 Inseraten je Achse): zusätzliche Zeile

> *⚠️ Stichprobenwarnung: Achse <X> basiert auf nur <n> Inseraten — Indikator-Wert mit Vorbehalt lesen.*

**Caveat bei kleinen Städten** (Pflicht wenn `plz_einwohner / stadt_einwohner > 0.7`):

> *Hinweis Stadt-Spezialfall: PLZ <plz> deckt ~<X> % der Stadt-EW ab — Stadtteil-Vergleich methodisch weniger trennscharf als in Großstädten. "Stadt-Aggregat"-Werte umfassen vermutlich Umkreis-Gemeinden.*

**Begriffe NICHT verwenden im User-Output:** "Top-Stadtteil", "Schwacher Stadtteil", "Top-Nachfrage", "Liquidität", "Eichung", "Score 0–10". Stattdessen neutrale Markt-Vergleichs-Sprache ("über Stadt-Schnitt", "spürbar schneller", "Indikator").

## 8. `objektdaten.json` schreiben

Vollständige Datei nach Schema in:

- Orchestrator-Modus: `runs/<slug>/objektdaten.json`
- Akquise-Modus: `<onedrive>/Immobilien/001_AQUISE/Objekte/<slug>/objektdaten.json`

**Schema-Validator-Lauf** (sobald `tools/validate_objektdaten.py` existiert — bis dahin manuelle Prüfung).

## 8.5 Pflicht-Check (Schritt P, Sub-Plan 6 ImmoCRM, seit 2026-05-27)

**Trigger:** läuft IMMER am Ende von Modul 1, in **beiden** Modi (Akquise + Orchestrator),
**nach** Schritt 8 (objektdaten.json schreiben) und **vor** Schritt 9 (state.json schreiben).
Reine LLM-Lese-Logik auf `objektdaten.json` — keine externen Tool-Aufrufe.

**Zweck:** stellt fest, ob die drei harten Pflicht-Felder für eine Aufteiler-
Bewertung bekannt sind. Bei Lücken setzt das CRM-Frontend später den Lead-
Status auf `offen` und schreibt eine System-Notiz mit Unterlagen-Anfrage an
den Makler (siehe ImmoCRM Sub-Plan 6, Task 11). Das CRM-Update selbst macht
Modul 0 in Schritt L.1 — Modul 1 protokolliert hier nur das Ergebnis im State.

### Pflicht-Felder

| Pflicht | Erfüllt wenn | Quelle in `objektdaten.json` |
|---|---|---|
| **Energie** | Energieklasse (A+ bis H) bekannt **ODER** Verbrauchswert in kWh/(m²·a) bekannt | `energieausweis.klasse.wert` ist gesetzt und ≠ `"unbekannt"` **ODER** `energieausweis.kennwert_kwh_qm_a.wert` ist gesetzt (`!= null`). Beide Pfade gelten als äquivalent — eine der beiden Quellen reicht. |
| **Mieten-Übersicht** | Anzahl Wohnungen + Kaltmiete pro Wohnung erkennbar | `we_liste[*].ist_miete_eur_monat.wert` — **mindestens 1** WE-Eintrag mit nicht-null Kaltmiete. Reine Wohnflächen ohne Mieten reichen NICHT. Im Schema 2.0 ist `ist_miete_eur_monat` der kanonische Pfad; ältere objektdaten-Files mit `kaltmiete_eur` werden alias-gelesen. |
| **Wohnfläche** | Gesamt-Wohnfläche in m² bekannt | `objekt.wohnflaeche_gesamt_qm.wert` ist gesetzt und `> 0`. Alternativ: Summe der WE-Wohnflächen (`Σ we_liste[*].wohnflaeche_qm.wert`) > 0 — beide Pfade gelten als äquivalent. |

### Ableitung `pflicht_check`

```python
fehlend = []

# Energie — Klasse ODER Verbrauchswert
energie_klasse = objektdaten.get("energieausweis", {}).get("klasse", {}).get("wert")
energie_verbrauch = objektdaten.get("energieausweis", {}).get("kennwert_kwh_qm_a", {}).get("wert")
if energie_klasse in (None, "", "unbekannt") and energie_verbrauch is None:
    fehlend.append("energie")

# Mieten — mindestens 1 WE mit Kaltmiete
we_liste = objektdaten.get("we_liste", [])
hat_miete = any(
    (we.get("ist_miete_eur_monat", {}).get("wert") is not None) or
    (we.get("kaltmiete_eur") is not None)   # Alias-Pfad älterer Schema-Versionen
    for we in we_liste
)
if not hat_miete:
    fehlend.append("mieten")

# Wohnfläche — gesamt ODER Summe WE
gesamt = objektdaten.get("objekt", {}).get("wohnflaeche_gesamt_qm", {}).get("wert")
summe_we = sum(
    we.get("wohnflaeche_qm", {}).get("wert", 0) or 0
    for we in we_liste
)
if (gesamt is None or gesamt <= 0) and summe_we <= 0:
    fehlend.append("wohnflaeche")

pflicht_status = "vollstaendig" if not fehlend else "unvollstaendig"
```

### Output in State

Beides — `fehlend` als Liste, `pflicht_status` als String — wird in
`state.json.modul_1.pflicht_check` geschrieben (siehe Schritt 9):

```json
"pflicht_check": {
  "status": "unvollstaendig",
  "fehlend": ["energie", "mieten"]
}
```

Bei vollständigen Pflicht-Daten:

```json
"pflicht_check": {
  "status": "vollstaendig",
  "fehlend": []
}
```

### Folgen für CRM

- `pflicht_check.status == "unvollstaendig"` → Modul 1 setzt in **Schritt 9.5 (Q)**
  selbst `deals.status='offen'`, ruft `makler-mail` mit Typ `unterlagen-anfrage`
  und schreibt eine `system_unterlagen_anfrage`-Notiz mit `mailto:`-URL.
- `pflicht_check.status == "vollstaendig"` → kein Status-Wechsel. Wenn ein
  vorheriger Lauf eine `system_unterlagen_anfrage`-Notiz hinterlassen hatte
  (Re-Lauf nach Nachreichung), schreibt Modul 1 in Schritt Q.4 zusätzlich eine
  `system_vollstaendig`-Erfolgs-Notiz. Bei Erst-Lauf ohne Mangel-Vorgeschichte
  passiert nichts (keine Lärm-Notiz).

**Wichtig (seit v3.6, 2026-05-27):** Modul 1 macht den CRM-Sync selbst —
siehe Schritt 9.5 (Q). Modul 0 setzt nach Modul-1-Rückkehr nur noch den
`priority_score` (oder `null` bei `pflicht_check.fehlend`). Hintergrund:
Schritt Q hat Makler-Email, Mängelliste und `deal_id` aus dem laufenden Modul-1-
Kontext direkt verfügbar — eine zweite Auslagerung in Modul 0 wäre
Datentransport ohne Nutzen.

## 9. State-Init / -Update

Datei: `runs/<slug>/state.json` (Orchestrator) bzw. `<slug>/state.json` (Akquise).

Minimal-State + `modul_1`-Block:

```json
{
  "schema_version": "2.0",
  "objekt": {
    "slug": "<slug>",
    "adresse": "<adresse_volltext>",
    "stadt": "<ort>",
    "bundesland": "NRW",
    "erstellt_am": "<iso>",
    "letzter_modul_lauf": "modul_1"
  },
  "modul_1": {
    "status": "<gruen|gelb|rot>",
    "ausgefuehrt_am": "<iso>",
    "objektdaten_pfad": "objektdaten.json",
    "angebotspreis_eur": <number>,
    "marktwert_konsens_eur": <number>,
    "gap_eur": <number>,
    "gap_prozent": <number>,
    "gap_ampel": "<gruen|gelb|rot>",
    "scoring_gesamt": <number 0-10>,
    "scoring_ampel": "<gruen|gelb|rot>",
    "konsens_quelle": "<n> von 4 Portalen",
    "konsens_spread_prozent": <number>,
    "eur_per_qm": {
      "homeday":                  <float|null>,
      "immometrica":              <float|null>,
      "check24":                  <float|null>,
      "interhyp":                 <float|null>,
      "grundstuecksmarktbericht": <float|null>,
      "median":                   <float|null>
    },
    "pflicht_check": {
      "status": "<vollstaendig|unvollstaendig>",
      "fehlend": ["<energie|mieten|wohnflaeche>", "..."]
    }
  }
}
```

**`pflicht_check`-Block (Pflicht, seit Sub-Plan 6 ImmoCRM, 2026-05-27):**
- `status`: aus Schritt 8.5 (P) — `"vollstaendig"` wenn alle drei Pflicht-
  Quellen erfüllt sind, sonst `"unvollstaendig"`.
- `fehlend`: leer-Array `[]` bei `status="vollstaendig"`. Sonst eine
  Teilmenge aus `["energie", "mieten", "wohnflaeche"]`. Reihenfolge: Energie,
  Mieten, Wohnfläche (stabile Reihenfolge für Frontend-Rendering).

`modul_1.status` aus `scoring.gesamt.ampel`:
- `gruen` → `gruen`
- `gelb` → `gelb`
- `rot` → `rot`

**Wichtig:** `eur_per_qm.*` weiterhin schreiben (Backwards-Compat zu Modul 5 Excel-Mapping `KALKU!I13–I17`).

## 9.5 CRM-Sync mit Pflicht-Check-Ergebnis (Schritt Q, Sub-Plan 6 ImmoCRM, seit v3.6 2026-05-27)

**Trigger:** läuft im **Akquise-Modus** direkt nach Schritt 9 (`state.json` mit
`modul_1`-Block geschrieben), **vor** Schritt 10 (Output-Block) und Schritt 11
(Akquise-Spezialitäten). Im **Orchestrator-Modus** wird Schritt Q übersprungen
(keine `deal_id` vorhanden, keine CRM-Anbindung).

**Modus-Check zu Beginn:**
```bash
DEAL_ID=$(jq -r '.modul_1.deal_id // empty' "$STATE_PATH")
if [ -z "$DEAL_ID" ]; then
  echo "[Schritt Q] kein deal_id in state.json — Orchestrator-Modus oder Modul 0 hat keinen Lead angelegt. Skip."
  # Weiter zu Schritt 10.
fi
```

**Voraussetzung:** Modul 0 (`aufteiler-modul-0-akquise-automatisierung`) hat
in Schritt I `deals.id` per `Prefer: return=representation` zurückbekommen
und in `state.json.modul_1.deal_id` geschrieben, bevor Modul 1 aufgerufen wurde.

**ENV-Variablen** (aus `.env` per ADR-006-Konvention, von Watcher/Modul 0 vererbt):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

### Q.0 Markt-Konsens €/m² in CRM schreiben (`deals.markt_pro_m2`)

**Läuft IMMER** wenn `deal_id` vorhanden ist — unabhängig vom Pflicht-Check-
Status. Schreibt den Markt-Konsens-€/m² aus der 4-Portale-Aggregation in die
CRM-Spalte `deals.markt_pro_m2`. Das ImmoCRM-Frontend rechnet daraus die
"% Markt"-Spalte (Abweichung des eigenen €/m² zum Marktdurchschnitt).

**Quelle:** `state.json.modul_1.eur_per_qm.median` — derselbe Konsens-Median,
der auch in Excel `KALKU!I13–I17` als Durchschnitt landet (4-Portale-Konsens,
siehe Memory `modul-0-portal-konsens`).

```bash
MARKT_PRO_M2=$(jq -r '.modul_1.eur_per_qm.median // empty' "$STATE_PATH")

if [ -n "$MARKT_PRO_M2" ]; then
  # Runden auf 2 Nachkommastellen (numeric-Spalte, vermeidet float-Rauschen)
  MARKT_PRO_M2=$(python -c "print(round(float('$MARKT_PRO_M2'), 2))")
  curl -sS -X PATCH "${SUPABASE_URL}/rest/v1/deals?id=eq.${DEAL_ID}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d "{\"markt_pro_m2\": ${MARKT_PRO_M2}}"
else
  echo "[Schritt Q.0] eur_per_qm.median ist null/leer — kein Markt-€/m² zum Schreiben. Skip."
  # Kein Abbruch: % Markt-Spalte bleibt leer, alle Portale lieferten null.
fi
```

**Idempotent:** Bei Re-Lauf wird `markt_pro_m2` mit demselben (oder aktualisierten)
Wert überschrieben — kein Duplikat, kein zweiter Eintrag. PATCH auf dieselbe
Spalte ist von Natur aus überschreibend.

**Warum nicht an `priority_score`/Lead-Insert (Modul 0) gekoppelt?** Der
Markt-€/m² steht erst nach der Portal-Pipeline + State-Write (Schritt 9) sicher
fest. Schritt Q hat `deal_id` und den fertigen State direkt verfügbar — die
natürliche Stelle, denselben Wert nach `deals.markt_pro_m2` zu spiegeln.

### Q.0b Objekt-Typ in CRM schreiben (`deals.object_type`)

**Läuft IMMER** wenn `deal_id` vorhanden ist — wie Q.0, unabhängig vom Pflicht-Check-
Status. Schreibt den Gebäudetyp als Kurzcode in die CRM-Spalte `deals.object_type`
(ImmoCRM zeigt ihn in der Spalte "Objekt"). `MFH` für ein ganzes Haus, `ETW` für eine
einzelne Eigentumswohnung — **keine Stückzahl** anhängen (die steht in der Spalte
"Einheiten").

**Quelle:** `objekt.objekttyp.wert` aus `objektdaten.json` (holistische Extraktion,
Schritt 8). **Autoritativ:** überschreibt idempotent einen evtl. abweichenden Best-
Effort-Wert aus dem Modul-0-Insert.

```bash
OBJ_PATH=$(jq -r '.modul_1.objektdaten_pfad // empty' "$STATE_PATH")
if [ -n "$OBJ_PATH" ] && [ -f "$OBJ_PATH" ]; then
  TYP=$(jq -r '(.objekt.objekttyp.wert // "") | ascii_downcase' "$OBJ_PATH")
  case "$TYP" in
    *eigentumswohnung*|wohnung|etw) OBJECT_TYPE="ETW" ;;
    *)                              OBJECT_TYPE="MFH" ;;
  esac
  curl -sS -X PATCH "${SUPABASE_URL}/rest/v1/deals?id=eq.${DEAL_ID}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d "{\"object_type\": \"${OBJECT_TYPE}\"}"
else
  echo "[Schritt Q.0b] kein objektdaten.json — object_type bleibt (Modul-0-Wert/leer). Skip."
fi
```

**Idempotent:** PATCH auf dieselbe Spalte — Re-Lauf überschreibt mit demselben (oder
korrigierten) Wert, kein Duplikat.

### Q.1 Status-Wechsel im CRM

```bash
PFLICHT_STATUS=$(jq -r '.modul_1.pflicht_check.status' "$STATE_PATH")

if [ "$PFLICHT_STATUS" = "unvollstaendig" ]; then
  curl -sS -X PATCH "${SUPABASE_URL}/rest/v1/deals?id=eq.${DEAL_ID}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d '{"status":"offen"}'
fi
```

Bei `pflicht_status="vollstaendig"`: **kein** Status-PATCH in Q.1 (der Lead behält
den Status, den Modul 0 / Owner zuletzt gesetzt hatte). Re-Lauf-Erfolgs-Notiz
kommt in Q.4.

**Owner-Entscheidung 2026-05-27 — Status wird IMMER auf "offen" gesetzt** bei
Lücke, auch wenn Owner den Lead zuvor manuell auf "berechnet" gesetzt hatte.
Konsequenz: nach Re-Lauf mit nun vollständigen Daten muss Owner manuell wieder
auf den gewünschten Status zurücksetzen — Modul 1 setzt **nicht** automatisch
auf "berechnet" zurück.

### Q.2 makler-mail-Skill aufrufen (nur bei `unvollstaendig`)

Mängelliste auf Deutsch aufbereiten (Schlüssel → User-facing Begriff):

| Schlüssel | Begriff für Mail-Body |
|---|---|
| `energie` | Energieausweis bzw. Energieeffizienzklasse |
| `mieten` | Mietaufstellung (Anzahl Wohnungen + Kaltmieten) |
| `wohnflaeche` | Wohnfläche in m² |

```bash
FEHLEND_DE=$(jq -r '.modul_1.pflicht_check.fehlend[]' "$STATE_PATH" \
  | sed 's/^energie$/Energieausweis bzw. Energieeffizienzklasse/' \
  | sed 's/^mieten$/Mietaufstellung (Anzahl Wohnungen + Kaltmieten)/' \
  | sed 's/^wohnflaeche$/Wohnfläche in m²/' \
  | paste -sd ', ')

FEHLEND_JSON_ARRAY=$(jq -c '.modul_1.pflicht_check.fehlend' "$STATE_PATH")

MAKLER_NAME=$(jq -r '.objekt.makler.name // "Makler"' "$STATE_PATH")
MAKLER_EMAIL=$(jq -r '.objekt.makler.email // empty' "$STATE_PATH")
OBJEKT_ADRESSE=$(jq -r '.objekt.adresse // empty' "$STATE_PATH")
```

Aufruf des `makler-mail`-Skills im **non-interactive-Modus** (kein Outlook-
Öffnen, kein `AskUserQuestion`, Skill gibt nur `mailto:`-URL als Plain-Text
zurück — siehe `Makler-Kommunikation/SKILL.md` Schritt 6 ab v1.1):

```
Skill(
  skill="makler-mail",
  args="unterlagen-anfrage --non-interactive=true --slug=<slug> --fehlend=\"${FEHLEND_DE}\""
)
```

Skill-Output (Plain-Text-Zeile, vom Caller per Regex aus stdout zu lesen):
```
MAILTO_URL=mailto:<email>?subject=...&body=...
```

In `$MAILTO_URL` einlesen. Falls Skill exit ≠ 0 oder Output ohne `MAILTO_URL=`-Zeile:
`MAILTO_URL=""` und Warnung in `meta.warnungen[]`. Notiz wird trotzdem
geschrieben (mit leerem `mailto_url` — Owner kann Mail manuell aufsetzen).

### Q.3 System-Notiz `system_unterlagen_anfrage` einfügen (idempotent)

**Idempotenz-Vorcheck:** prüfe, ob aus den letzten 24h schon eine ungelesene
`system_unterlagen_anfrage`-Notiz für diesen Deal existiert. Wenn ja → existierende
Notiz mit neuer `mailto_url` updaten, statt zweite Notiz anzulegen.

```bash
ISO_24H_AGO=$(python -c "import datetime,sys; print((datetime.datetime.utcnow()-datetime.timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ'))")

EXISTING_NOTE_ID=$(curl -sS \
  "${SUPABASE_URL}/rest/v1/deal_notes?deal_id=eq.${DEAL_ID}&kind=eq.system_unterlagen_anfrage&read_at=is.null&created_at=gte.${ISO_24H_AGO}&order=created_at.desc&limit=1&select=id" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
  | jq -r '.[0].id // empty')

CONTENT_HTML="<p>Autoanalyse unvollständig, es fehlt: ${FEHLEND_DE}.</p>"

# JSON-Body via jq bauen (sicher gegen Sonderzeichen in Adresse / Makler-Name)
BODY_JSON=$(jq -n \
  --arg deal_id      "$DEAL_ID" \
  --arg content_html "$CONTENT_HTML" \
  --argjson fehlend  "$FEHLEND_JSON_ARRAY" \
  --arg mailto       "$MAILTO_URL" \
  --arg name         "$MAKLER_NAME" \
  --arg email        "$MAKLER_EMAIL" \
  '{
    deal_id:      $deal_id,
    content_html: $content_html,
    kind:         "system_unterlagen_anfrage",
    metadata: {
      fehlende_pflichtdaten: $fehlend,
      mailto_url:            $mailto,
      empfaenger_name:       $name,
      empfaenger_email:      $email
    },
    read_at: null
  }')

if [ -n "$EXISTING_NOTE_ID" ]; then
  # Idempotent: nur metadata.mailto_url + content_html aktualisieren
  UPDATE_JSON=$(jq -n \
    --arg content_html "$CONTENT_HTML" \
    --argjson fehlend  "$FEHLEND_JSON_ARRAY" \
    --arg mailto       "$MAILTO_URL" \
    --arg name         "$MAKLER_NAME" \
    --arg email        "$MAKLER_EMAIL" \
    '{
      content_html: $content_html,
      metadata: {
        fehlende_pflichtdaten: $fehlend,
        mailto_url:            $mailto,
        empfaenger_name:       $name,
        empfaenger_email:      $email
      }
    }')
  curl -sS -X PATCH "${SUPABASE_URL}/rest/v1/deal_notes?id=eq.${EXISTING_NOTE_ID}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d "$UPDATE_JSON"
else
  curl -sS -X POST "${SUPABASE_URL}/rest/v1/deal_notes" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: return=minimal" \
    -d "$BODY_JSON"
fi
```

`read_at: null` ist Pflicht — Notiz ist neu und ungelesen, blau-leuchtend in der
Lead-Tabelle.

### Q.4 Re-Lauf-Erkennung — Erfolgs-Notiz bei nun vollständigen Daten

Nur bei `pflicht_status="vollstaendig"`. Prüfen, ob es **irgendwann** eine
`system_unterlagen_anfrage`-Notiz auf diesem Deal gab (Audit-Spur — auch wenn
sie inzwischen als gelesen markiert ist). Wenn ja → dieser Lauf ist ein
**Re-Lauf nach Nachreichung**, eine `system_vollstaendig`-Erfolgs-Notiz wird
angehängt.

```bash
if [ "$PFLICHT_STATUS" = "vollstaendig" ]; then
  PREV_NOTE=$(curl -sS \
    "${SUPABASE_URL}/rest/v1/deal_notes?deal_id=eq.${DEAL_ID}&kind=eq.system_unterlagen_anfrage&order=created_at.desc&limit=1&select=metadata" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}")

  PREV_FEHLEND=$(echo "$PREV_NOTE" | jq -c '.[0].metadata.fehlende_pflichtdaten // empty')

  if [ -n "$PREV_FEHLEND" ] && [ "$PREV_FEHLEND" != "empty" ]; then
    HEUTE=$(date +%d.%m.%Y)
    BODY_JSON=$(jq -n \
      --arg deal_id   "$DEAL_ID" \
      --arg heute     "$HEUTE" \
      --argjson prev  "$PREV_FEHLEND" \
      '{
        deal_id:      $deal_id,
        content_html: ("<p>Autoanalyse vollständig am " + $heute + ". Alle zuvor fehlenden Unterlagen sind jetzt vorhanden.</p>"),
        kind:         "system_vollstaendig",
        metadata:     { zuvor_fehlend: $prev },
        read_at:      null
      }')
    curl -sS -X POST "${SUPABASE_URL}/rest/v1/deal_notes" \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Content-Type: application/json" \
      -H "Prefer: return=minimal" \
      -d "$BODY_JSON"
  fi
fi
```

**Wichtig (Owner-Entscheidung 2026-05-27):**
- Die alte `system_unterlagen_anfrage`-Notiz bleibt **unverändert stehen** —
  als Audit-Spur. Sie wird **nicht** gelöscht und **nicht** überschrieben.
- Beim Erst-Lauf ohne vorherige Mangel-Notiz wird **keine** `system_vollstaendig`-
  Notiz erzeugt — das wäre Lärm.
- Der Lead-Status wird in Q.4 **nicht** automatisch von "offen" zurück auf
  "berechnet" gesetzt — Owner entscheidet manuell, ob ein Re-Lauf für ihn
  bereits "abgehakt" ist (siehe Q.1 Owner-Entscheidung).

### Q-Phase Self-Check

- [ ] **(Q.0)** Falls `eur_per_qm.median` gesetzt: PATCH `deals.markt_pro_m2` HTTP 2xx (Wert auf 2 Nachkommastellen gerundet). Bei `median=null`: bewusst übersprungen (kein Fehler).
- [ ] Falls `pflicht_status="unvollstaendig"`: PATCH `deals.status='offen'` HTTP 2xx
- [ ] Falls `pflicht_status="unvollstaendig"`: `makler-mail`-Skill aufgerufen, `MAILTO_URL` extrahiert (oder leer + Warnung)
- [ ] Genau **eine** `system_unterlagen_anfrage`-Notiz pro Deal in den letzten 24h (Idempotenz-Vorcheck respektiert)
- [ ] Falls `pflicht_status="vollstaendig"` UND vorherige Mangel-Notiz existiert: genau eine `system_vollstaendig`-Erfolgs-Notiz angehängt (Q.4)
- [ ] `read_at: null` bei jeder neu eingefügten Notiz

## 10. Output-Block (Quick-Layout, schlank — seit v2.1)

In `modul-0-output.md` UND im Terminal-Output, in dieser Reihenfolge:

### 10.1 Daten-Check

```
============================================================
DATEN-CHECK
============================================================
Vorhanden: <kommagetrennt aus meta.daten_check.vorhanden>
Fehlend:   <kommagetrennt aus meta.daten_check.fehlend>
ANNAHMEN:
  - <feld>: <wert>  (ANNAHME: <begründung>, Konfidenz: <niedrig|mittel|hoch>)
  ...
```

Wenn `annahmen[]` leer: Zeile "ANNAHMEN: keine" ausgeben.

### 10.2 Schnellkennzahlen

Aus `markt.eckdaten`:

```
============================================================
SCHNELLKENNZAHLEN
============================================================
| Kennzahl              | Wert        | Benchmark      |
|-----------------------|-------------|----------------|
| Kaufpreis             | <eur>       |                |
| Gesamtwohnfläche      | <qm>        |                |
| €/m² Kaufpreis        | <eur>       | PLZ-Median <eur> (<sign><pct>%)|
| Mietmultiplikator     | <x.x>       | <15 sehr gut / 15-20 ok / >20 teuer|
| Brutto-Mietrendite    | <pct>%      | >6 % sehr gut / 4-6 % ok / <4 % schwach|
| Kaufnebenkosten (NRW) | <eur>       | 12 %           |
| Gesamtinvest          | <eur>       |                |
| Ziel-Aufteilungserlös | <eur>       | Faktor 14 × Jahres-Kaltmiete|
| Aufteilungs-Spread    | <sign><pct>%| ≥+25 % Zielwert|
```

### 10.3 Cashflow

Aus `markt.cashflow`:

```
============================================================
CASHFLOW  (80 % Beleihung, 6 % Annuität, 20 % BWK-Pauschale)
============================================================
Beleihungspotenzial:   <eur>
Eigenkapital:          <eur>    (= KP × 20 % + KNK)
Jahres-Annuität:       <eur>

                       IST          SOLL (Mietspiegel)
Jahres-Kaltmiete       <eur>        <eur>
- BWK 20 %             <eur>        <eur>
- Annuität             <eur>        <eur>
= Cashflow vor Steuer  <eur>        <eur>
Cashflow-Rendite EK    <sign><pct>% <sign><pct>%

Mietsteigerungspotenzial: <sign><pct>%
```

Wenn Ist-Miete = Soll-Miete (Annahme): IST-Spalte mit `(= Soll, ANNAHME)`-Marker.

### 10.4 Markt-Vergleich PLZ vs. Stadt

Aus `markt.portale.immometrica`:

```
============================================================
MARKT-VERGLEICH PLZ vs. STADT  (H1/2026)
============================================================
                         PLZ          Stadt        Δ
ETW Kauf  €/m²           <eur>        <eur>        <sign><pct>%
ETW Kauf  Inserate       <n>          <n>          PLZ = <pct>%
ETW Kauf  Vermarkt-Tage  <n>          <n>          PLZ <sign><pct>%
Miete     €/m²/Mo        <eur>        <eur>        <sign><pct>%
Miete     Inserate       <n>          <n>          PLZ = <pct>%
Miete     Vermarkt-Tage  <n>          <n>          PLZ <sign><pct>%
------------------------------------------------------------
MFH-Gap PLZ              <eur>/m²     (<sign><pct>% vs ETW-PLZ)
GMB-Lage-Klasse          <gut|mittel|mäßig>  (gut <eur> / mittel <eur> / mäßig <eur>)
GMB-Marktdruck           <pct>% Miete / <pct>% Eigentum
```

### 10.5 Sub-Markt — Vermarktungsdauer pro WE-Typ

Aus `markt.portale.immometrica.etw_verkauf.dimensionale_sub_charts.plz.pro_zimmerklasse` + `markt.portale.immometrica.miete.dimensionale_sub_charts.plz.pro_zimmerklasse`:

```
============================================================
SUB-MARKT — Vermarktungsdauer ETW PLZ pro WE-Typ
============================================================
              Verkauf-Tage   Miete-Tage
1-Zi          <n>            <n>
2-Zi          <n>            <n>
3-Zi          <n>            <n>
4-Zi+         <n>            <n>
(Volle €/m² + Inserate-Anzahl pro Bucket in objektdaten.json)
```

### 10.6 Lage-Sub-Score-Detail (Pflicht-Ausformulierung seit v3.1)

**Verbindliches Format (seit 2026-05-26 v3.1):** Jede k-Komponente
muss ausformuliert sein mit (a) absoluten Inputs PLZ + Stadt,
(b) Premium/Ratio in %, (c) Formel mit Zwischenwert, (d) Lese-Sinn
in einem Satz, (e) Gewicht im Lage-Gesamtscore. Quelle obligatorisch.

```
============================================================
LAGE-SUB-SCORE: <X,XX> / 10  (6-dim Variante B inkl. GMB)
============================================================
Alle k-Werte auf 0-10 normiert. 5,0 = neutral / Marktschnitt.
Quelle aller Markt-Inputs: Immometrica-Pipeline H1/<halbjahr> (außer k6).

──────────────────────────────────────────────────────────────
k1  VERKAUFS-PREMIUM PLZ vs. STADT                Wert <X,XX> / 10
──────────────────────────────────────────────────────────────
    PLZ <plz> (ETW-Kauf):    <X> €/m²  (<n> Inserate)
    <stadt> (ETW-Kauf):      <Y> €/m²  (<m> Inserate)
    Premium PLZ:             <+/-X,XX> % gegenüber Stadt/Kreis
    Formel:                  clamp(0, 10, 5 + <premium%>/4)
                             = 5 + <Z> = <X,XX>
    Lese-Sinn:               <ein-satz-deutung>
    Gewicht in Lage-Score:   0,22

──────────────────────────────────────────────────────────────
k2  MIETEN-PREMIUM PLZ vs. STADT                  Wert <X,XX> / 10
──────────────────────────────────────────────────────────────
    PLZ <plz> (Miete):       <X> €/m²/Mo  (<n> Inserate)
    <stadt> (Miete):         <Y> €/m²/Mo  (<m> Inserate)
    Premium PLZ:             <+/-X,XX> % gegenüber Stadt/Kreis
    Formel:                  clamp(0, 10, 5 + <premium%>/4)
                             = 5 + <Z> = <X,XX>
    Lese-Sinn:               <ein-satz-deutung>
    Gewicht in Lage-Score:   0,18

──────────────────────────────────────────────────────────────
k3  VERKAUFS-LIQUIDITÄT (Vermarktungsdauer)       Wert <X,XX> / 10
──────────────────────────────────────────────────────────────
    PLZ <plz>:               <n> Tage online (ETW-Median)
    <stadt>:                 <m> Tage online
    Ratio:                   <+/-X,XX> % (PLZ <länger|kürzer> online)
    Formel:                  clamp(0, 10, 5 − <ratio%>/8)
                             = 5 - <Z> = <X,XX>
    Lese-Sinn:               <ein-satz-deutung>
    Gewicht in Lage-Score:   0,18

──────────────────────────────────────────────────────────────
k4  MIETER-NACHFRAGE (Miet-Vermarktungsdauer)     Wert <X,XX> / 10
──────────────────────────────────────────────────────────────
    PLZ <plz>:               <n> Tage online (Miet-Median)
    <stadt>:                 <m> Tage online
    Ratio:                   <+/-X,XX> % (PLZ <länger|kürzer> online)
    Formel:                  clamp(0, 10, 5 − <ratio%>/8)
                             = <Z> [→ <wert>] (bei Clamp: "(capped)")
    Lese-Sinn:               <ein-satz-deutung>
    Gewicht in Lage-Score:   0,17

──────────────────────────────────────────────────────────────
k5  MARKT-TIEFE (PLZ-Anteil an Stadt-Inseraten)   Wert <X,XX> / 10
──────────────────────────────────────────────────────────────
    ETW-Anteil PLZ:          <n_etw> / <m_etw> = <X,XX> % der Stadt-Inserate
    Miet-Anteil PLZ:         <n_miete> / <m_miete> = <Y,YY> % der Stadt-Inserate
    Durchschnitt:            <Ø> %
    Formel:                  clamp(0, 10, <Ø>%/3) = <X,XX>
    Lese-Sinn:               <ein-satz-deutung>
    Gewicht in Lage-Score:   0,10

──────────────────────────────────────────────────────────────
k6  GMB-LAGE-KLASSE                              Wert <X,XX> / 10
──────────────────────────────────────────────────────────────
    Status:                  <klasse: gut/mittel/mäßig|null mit Begründung>
    Default bei null:        5 (neutral)
    Lese-Sinn:               <ein-satz-deutung>
    Gewicht in Lage-Score:   0,15

──────────────────────────────────────────────────────────────
SUMME = k1*0,22 + k2*0,18 + k3*0,18 + k4*0,17 + k5*0,10 + k6*0,15
      = <berechnung-mit-zwischenwerten>
      = <X,XX>
──────────────────────────────────────────────────────────────
AMPEL: ≥7,0 grün · 4,0–6,9 gelb · <4,0 rot
     <X,XX> → <emoji> <FARBE> <"X Punkte unter/über Schwelle">
```

**Anti-Pattern:** Eine k-Komponente NUR mit Zahl + Kurz-Hinweis
("k1 Verkaufs-Premium : 6,69  (PLZ-ETW +6,76 %)") ist
**nicht ausreichend**. Der User muss aus dem Block heraus
(ohne in objektdaten.json zu schauen) verstehen können:
- Was wird verglichen? (PLZ vs. Stadt, ETW vs. Miete, etc.)
- Welche absoluten Werte stecken dahinter?
- Welche Formel ergibt aus diesen Werten den k-Score?
- Wie soll man die Zahl lesen? (Lese-Sinn-Satz)

### 10.7 Score-Overview (bestehender 5-Sub-Score-Block)

```
============================================================
SCORE-OVERVIEW — <adresse_volltext>
============================================================

GESAMT: <X.X> / 10    <ampel-emoji>  <kurz_fazit>

┌─────────────────┬───────┬──────────────────────────────────┐
│ Dimension       │ Score │ Begründung                       │
├─────────────────┼───────┼──────────────────────────────────┤
│ Lage            │ <X.X> │ <emoji> <begruendung_lage>       │
│ Miet-Potenzial  │ <X.X> │ <emoji> <begruendung_miete>      │
│ Energie         │ <X.X> │ <emoji> <begruendung_energie>    │
│ Zustand         │ <X.X> │ <emoji> <begruendung_zustand>    │
│ Deal-Gap        │ <X.X> │ <emoji> <begruendung_deal>       │
└─────────────────┴───────┴──────────────────────────────────┘

Markt-Konsens:    <X> € (Median <n> Portale, Spread <X>%)
Angebot:          <X> € (<+/-X.X>%)
Mietmultiplikator: <X.X> × IST-JNKM
```

**Direkt nach dem Score-Overview-Block (seit v3.1) folgt OBLIGATORISCH ein
ausformulierter "BEGRÜNDUNGEN PRO SUB-SCORE"-Block** — die ASCII-Box
gibt nur den 30-Sekunden-Überblick, die ausformulierte Begründung darunter
ist der eigentliche Nachvollziehbarkeits-Anker:

```
──────────────────────────────────────────────────────────────
BEGRÜNDUNGEN PRO SUB-SCORE (jede Zahl mit Bezugsgröße + Quelle)
──────────────────────────────────────────────────────────────

LAGE (6-dim) — <X,XX> / 10 <emoji>
    Siehe Lage-Sub-Score-Detail-Block oben (k1-k6 mit Formeln).

MIET-POTENZIAL — <X,XX> / 10 <emoji>
    IST-Schnitt:        <X> €/m²/Mo
    Berechnung:         <jahres_kalt> € / <wfl> m² / 12 Monate
                        (Quelle: <expose-seite> — Hinweis ggf.
                        "inkl. Garagen-Anteil")
    Ziel-Miete:         <Z> €/m²/Mo  (<ziel_quelle>)
                        ziel_quelle = mietspiegel_obergrenze (§558-Maximum,
                        Priorität — legaler Hebel auf Bestandsmieter) ODER
                        immometrica_miete_plz_median (Fallback bei
                        Mietspiegel-DB-Lücke — realistische Neuvermietung)
    Cross-Check:        Markt-Median Immometrica PLZ <plz>: <Y> €/m²/Mo
                        (<n> Inserate, H1/<halbjahr>)
                        — nur zur Plausibilisierung, nicht Ziel-Wert wenn
                        Mietspiegel-Obergrenze vorhanden
    Potenzial:          (<Z> / <X> − 1) × 100 = <+/-P> %
    Hebel absolut:      (<Z> − <X>) × <wfl> m² × 12 Mo
                        = <delta_jahr> € / Jahr Mehr-Kaltmiete bei voller
                        Ausschöpfung der Ziel-Miete
    Formel:             clamp(0, 10, <potenzial%>/5) = <X,XX>
                        (50% Hebel → 10 P · 25% → 5 P · 10% → 2 P)
    Lese-Sinn:          <ein-satz-deutung>
    Ampel-Schwelle:     ≥6 grün · 3-6 gelb · <3 rot
    Achtung-Annahme:    <falls Mietspiegel-DB fehlt: Warnung dass Markt-Median
                        als Fallback genutzt wurde + Hinweis dass Modul 6
                        präzisieren wird>

ENERGIE — <X,XX> / 10 <emoji>
    Endenergiebedarf:   <kWh/m²a> (<Quellen-Datei>)
                        <ggf. zweiter Wert für Nachbar-Gebäude>
    Klasse:             <A+..H> (höchste = schlechteste GEG-Skala A+ bis H)
    Energieträger:      <Gas/Öl/Pellet/etc.>
                        (<Bedarfsausweis | Verbrauchsausweis>)
    Ausstellungsdatum:  <YYYY-MM-DD> (gültig bis <YYYY-MM-DD>)
    Score-Mapping:      A+ / A / B / C = 10 (Cap — C oder besser = voller Score)
                        D = 9 · E = 7 · F = 5 · G = 3 · H = 1
                        unbekannt = 5 (neutral)
                        Stützpunkte: C=10, D=9, H=1 (User-Vorgabe),
                        dazwischen linear (Δ=2 pro Stufe)
    Quelle:             <Energieausweis.pdf-Seite, Reg-Nr>
    Lese-Sinn:          <ein-satz-deutung + ggf. GEG-§72-Hinweis>
    Ampel-Schwelle:     ≥7 grün (D+) · 4-7 gelb · <4 rot

ZUSTAND — <X,XX> / 10 <emoji>
    Modernisierte Gewerke (<n> von 8):
      <Gewerk_1> — <jahr_oder_zeitraum>  (Quelle: <pdf>:<seite>)
      <Gewerk_2> — ...
      ...
    Offene Gewerke (<8-n> von 8):
      <Liste der Gewerke ohne jahr-Beleg>
    mod_score:          <n> / 8 × 10 = <X,XX>
    Zustand-Bonus:      <+/-N> Punkte
                        Begründung: ausstattung.zustand_innen =
                        "<wert>" laut <Quelle>
    Endgültig:          clamp(0, 10, <mod_score> + <bonus>) = <X,XX>
    Lese-Sinn:          <ein-satz-deutung>
    Ampel-Schwelle:     ≥7 grün · 4-7 gelb · <4 rot

DEAL-GAP — <X,XX> / 10 <emoji>
    Angebotspreis:      <X> €  (<expose-quelle>)
    ETW-Aufteilungs-Konsens (Marktwert-Total):
                        <wfl> m² × <median> €/m² = <Y> €
    Median-Berechnung:  <n> Portale
                          <portal>: <wert> €/m²
                          ...
                          → Median: <X> €/m²
    Gap (Total):        <angebot> − <konsens> = <delta> €
    Gap (Prozent):      <+/-Z> % (Angebot <UNTER|ÜBER> Konsens)
    Formel:             clamp(0, 10, 5 − <gap%>/3)
                        = clamp(5 - (<gap%>)/3)
                        = <berechnung> [→ <wert>] (bei Clamp: "(capped)")
    Lese-Sinn:          <ein-satz-deutung + ggf. CapEx-Hinweis>
    Ampel-Schwelle:     ≥6 grün · 3-6 gelb · <3 rot

──────────────────────────────────────────────────────────────
GESAMT-SCORE-BERECHNUNG
──────────────────────────────────────────────────────────────
    Mittelwert: (<l> + <m> + <e> + <z> + <d>) / 5 = <X,XX>
    Penalty-Regel: Wenn ≥2 Sub-Scores rot → Gesamt-Ampel rot
                   <falls Penalty greift: welche 2 sind rot>
                   → Gesamt-Ampel = ROT (Override)
                   <falls keine Penalty: Penalty greift nicht>
    Ampel ohne Penalty: <X,XX> wäre <emoji> <farbe> (Schwelle <s>)
    Ampel mit Penalty:  <emoji> <farbe>
    Kurz-Fazit:         "<kurz_fazit>"

Datenbasis: objektdaten.json (vollständig annotiert)
Stand: H1/<halbjahr> | Baujahr-Filter 1900–1980 | Modul 1 v3.1

Weiter mit Modul 2 (Objektbasis) ? — j/n
============================================================
```

**Emoji-Mapping:**
- `gruen` → 🟢
- `gelb` → 🟡
- `rot` → 🔴

**KEIN VERDICT-Block, KEINE 5-Dim-Ampel-Matrix, KEINE Risiko-Liste, KEINE Next-Steps, KEIN Bias-Scan** — Modul 1 ist bewusst schlanker Daten-Quick-Check.

**Aber:** Der "BEGRÜNDUNGEN PRO SUB-SCORE"-Block (seit v3.1) ist Pflicht — er ist
das primäre Audit-Artefakt. Wenn er fehlt, ist der Output ungültig.

### 10.8 Block-Layout `quickcheck.md` (für User-Lade-Darstellung, seit 2026-05-26 v3.0)

**Zusätzlich** zum vollen Output-Block (10.1–10.7) schreibt Modul 1 ein
kompaktes Block-Layout in `<lead>/quickcheck.md` — das ist die User-facing
Lade-Darstellung mit Ampel-Smileys 🟢🟡🔴 und fettgedruckten Kennwerten.
Keine `=====`-Trennbalken; Blöcke werden durch Emoji-Überschriften + Leerzeile
getrennt. Keine Maklerinfo, keine Annahmen-Liste, keine Audit-Spur (die
gehören in `.aufteiler/quickcheck-log.md`).

**Block-Reihenfolge (fest):**

1. 🎯 **Empfehlung**
2. 📊 **Scoring**
3. 💰 **Konsens**
4. ⚖️ **Verdikt** (Gap + Marktpreis)
5. 🏠 **Objektdaten & Risiken**
6. Abschluss-Frage

#### Block 1 — 🎯 Empfehlung

```markdown
### 🎯 Empfehlung

| Punkt | Wert |
|---|---|
| Verdict | <Ampel> **<Vollanalyse / Verhandeln / Skip>** |
| Erstangebot | **<X> €** (<-Y %> zum Konsens) |
| Upside | <ein kurzer Hinweis, z.B. „Gewerbe + Stellplätze on top"> |
```

Verdict-Mapping (Score-Skala 0–10):
- Score ≥ 7 → "Vollanalyse"
- Score 4–6,9 → "Verhandeln"
- Score < 4 → "Skip"

Erstangebot = `angebotspreis_eur`. Prozent in Klammern = `gap_prozent` (mit Vorzeichen: negativ = unter Konsens, positiv = über).

Upside-Zeile: ein Bullet aus den erkannten Extras (Stellplätze ≥ 2, Garagen ≥ 1, Gewerbe-WE erkannt, Ausbaureserve aus Bauzeichnungen). Wenn nichts → Zeile weglassen.

#### Block 2 — 📊 Scoring (0–10)

```markdown
### 📊 Scoring

| Position | Wert |
|---|:---:|
| Gesamt-Score | <Ampel> **<N,N> / 10** |
| Status | <Ampel> **<GRÜN / GELB / ROT>** |

**Sub-Scores (5-Dim, v3.1)** — jede Zahl mit Bezugsgröße + Quelle:

#### Lage (6-dim) — Score **<X,X> / 10** <emoji>

<2-3-Sätze: PLZ X % teurer/billiger pro m² als Stadt/Kreis (absolute
Werte beide), Mietwohnungen X % höher (absolute Werte beide),
Vermarktungsdauer Miete <a> Tage vs. <b> Tage, GMB-Klasse oder
Hinweis warum nicht verfügbar.>
**Quelle:** Immometrica-Pipeline H1/<halbjahr> (<n> ETW + <m> Miet-Inserate).

#### Miet-Potenzial — Score **<X,X> / 10** <emoji>

IST-Schnitt: **<X> €/m²/Mo** (aus <jahres_kalt> € Jahresnetto /
<wfl> m² / 12 Monate, Quelle: Exposé S.<seite>; ggf. Hinweis
"inkl. Garagen").
Ziel-Miete: **<Z> €/m²/Mo** (<ziel_quelle> — Mietspiegel-Obergrenze §558
ODER, bei DB-Lücke, Immometrica-Miete PLZ <plz> H1/<halbjahr>, <n> Inserate).
Cross-Check Markt-Median PLZ: **<Y> €/m²/Mo** (Immometrica).
Potenzial = (<Z> / <X> − 1) × 100 = **<+/-P> %**.
Hebel absolut: bei voller Ausschöpfung **+<delta_jahr> € / Jahr** Mehr-Kaltmiete.
Formel `clamp(0, 10, potenzial%/5)` — 50 % Hebel = volle 10 P, 25 % = 5 P.
<Falls Mietspiegel-DB-Lücke: kurzer Hinweis dass Markt-Median als Fallback
genutzt wurde und Modul 6 präzisieren wird>

#### Energie — Score **<X,X> / 10** <emoji>

Endenergiebedarf **<kWh/m²a> — Klasse <A+..H>** (<Adjektiv:
höchste/beste/etc.>). Score-Tabelle: A+/A/B/**C = 10** · **D = 9** · E = 7 ·
F = 5 · G = 3 · **H = 1** (Stützpunkte C/D/H, dazwischen linear).
<Ein-Satz-Deutung — z.B. ungedämmt, GEG-Risiko, etc.>
**Quelle:** Energieausweis <datum>, <Bedarfs|Verbrauchs>-Ausweis.

#### Zustand — Score **<X,X> / 10** <emoji>

<n> von 8 ImmoWertV-Gewerken nachweislich modernisiert:
**<Gewerk_1> <jahr>, <Gewerk_2> <jahr>, ...** → Basis: <n>/8 × 10 = <X,XX>.
<+/-N> Punkte <bonus|malus> wegen <Zustands-Quote aus Exposé>
→ **<endgültig>**. Offene Gewerke: <Liste>.
**Quelle:** Exposé S.<seite>.

#### Deal-Gap — Score **<X,X> / 10** <emoji>

Angebot **<X> €** vs. ETW-Aufteilungs-Konsens **<Y> €** (= <wfl> m² ×
**<median> €/m²** Median aus <portal1> <wert1> / <portal2> <wert2> /
<portal3> <wert3>) → Angebot liegt **<+/-Z> %** <unter|über> Konsens.
Formel `clamp(0, 10, 5 − gap%/3)` = <berechnung> → <wert> <ggf "(capped)">.
<Ein-Satz-Deutung zum Hebel-Potential ggf. mit CapEx-Hinweis>
```

Skala Gesamt-Score: 🟢 ≥ 7 = kaufen · 🟡 4–6,9 = verhandeln · 🔴 < 4 = skip.

**Anti-Pattern für Block 2 (seit v3.1):** EIN-Wort-Begründungen wie
"Klasse H, 357 kWh/m²a" oder "PLZ-ETW +7%, Miete-PLZ +10%, GMB n/v"
sind **nicht ausreichend**. Der User muss den Block ohne Rückgriff auf
`objektdaten.json` lesen können und nachvollziehen:
- WORAUF bezieht sich die Prozentzahl? (absolute Werte beider Seiten)
- WOHER kommt die Zahl? (Datei, Tool, Portal mit Stand)
- WIE wird sie zum Score? (Formel mit Zwischenwert)

#### Block 3 — 💰 Konsens (Marktwert-Quellen)

```markdown
### 💰 Konsens

| Quelle | €/m² |
|---|---:|
| Homeday Atlas | **<…>** |
| Immometrica PLZ-ETW | **<…>** |
| CHECK24 | **<…>** |
| Interhyp | **<…>** |
| GMB (Notion) | **<…>** oder „offen" |
| **Median** | **<…>** |
```

Werte kommen 1:1 aus `modul_1.eur_per_qm.*`. Bei `null` schreiben „offen".

Darunter eine Zeile:

```markdown
**Marktwert-Konsens (Wohnanteil):** <X> € · **Angebotspreis:** <Y> €
```

#### Block 3.5 — 📍 Stadtteil-Vergleich (seit v3.2, 5. Achse seit v3.3)

Position: direkt zwischen `💰 Konsens` und `⚖️ Bewertung`.

Verbindliches Format — **alle Spalten linksbündig** (User-Wunsch v3.2), **Bewertungs-Spalte ganz vorn** (User-Wunsch v3.3):

```markdown
### 📍 Stadtteil-Vergleich (PLZ <plz> vs. Stadt <ort>)

| Bewertung                                | Achse                          | PLZ <plz>   | Stadt <ort> |
|:-----------------------------------------|:-------------------------------|:------------|:------------|
| <Ampel> **<+/-X %>** — <wort-einordnung> | Verkaufspreis €/m²             | **<x> €**   | **<y> €**   |
| <Ampel> **<+/-X %>** — <wort-einordnung> | Mietpreis €/m²/Mo              | **<x> €**   | **<y> €**   |
| <Ampel> **<+/-X %>** — <wort-einordnung> | Vermarktungsdauer Verkauf      | **<n> d**   | **<m> d**   |
| <Ampel> **<+/-X %>** — <wort-einordnung> | Vermarktungsdauer Vermietung   | **<n> d**   | **<m> d**   |
| <Ampel> **<+X %>** — <wort-einordnung>   | Aufteilungs-Premium PLZ        | **<x> €**   | —           |

**Indikator:** <Ampel> **<wort>** — <n> von <m> Achsen grün

*Hinweis: Markt-Vergleichs-Indikator auf Basis Immometrica-Snapshot H1/<halbjahr> (Baujahr-Filter 1900–1980). **Ersetzt keine qualitative Lage-Bewertung** (Mikrolage, ÖPNV, Lärm, Einkauf, Schulen) — diese kommen aus Mietspiegel-Lage-Zuschlag (Modul 6) und ggf. Notion-GMB-Lage-Klasse. Stichproben: <n_etw>/<m_etw> ETW-Inserate (Verkauf), <n_miete>/<m_miete> Miet-Inserate (Miete) — Median kann bei wenigen Inseraten durch Ausreißer gezogen werden.*

<ggf-stichproben-warnung-wenn-< 30-inserate-irgendwo>
<ggf-caveat-wenn-plz/stadt-ew-überlapp-> 0.7>
```

**Achse 5 (Aufteilungs-Premium PLZ) — Sonderlogik:**

- **Quelle:** `markt.portale.immometrica.mfh_gap.gap_prozent`. Aufteilungs-Premium = `-gap_prozent` (positive Zahl = ETW teurer als MFH-Paket = Aufteilungs-Spread).
- **PLZ-Spalte:** zeigt MFH-€/m² (`markt.portale.immometrica.mfh.plz.median_eur_pro_qm`). Stadt-Spalte zeigt `—` (Stadt-MFH-Werte sind separat in Section 7.7 dokumentiert, aber für die PLZ-Premium-Sicht nicht relevant).
- **Bewertungs-Spalte:** Ampel + Wert nur wenn alle drei Bedingungen erfüllt:
  1. `mfh.plz.inserate_anzahl ≥ 3`
  2. `mfh.plz.median_eur_pro_qm != etw_verkauf.plz.median_eur_pro_qm` (Quirk A — ETW-Wert geleckt)
  3. `mfh.plz.median_eur_pro_qm ≥ 200` (Quirk B — Miete-Wert geleckt; Miete in €/m²/Mo ist typisch < 30, Kaufpreis-MFH > 1.000)
- **Fallback `n/v`:**
  - Wenn `mfh.plz.median_eur_pro_qm == etw_verkauf.plz.median_eur_pro_qm` → `⚪ n/v — Tool-Quirk (MFH=ETW)` und Zeile wird im Indikator-Zähler **übersprungen** (m = 4 statt 5).
  - Wenn `mfh.plz.median_eur_pro_qm < 200` → `⚪ n/v — Tool-Quirk (Miete-Wert geleckt)` und Zeile wird **übersprungen**.
  - Wenn `mfh.plz.inserate_anzahl < 3` → `⚪ n/v — zu wenig Inserate (<n>)` und Zeile wird **übersprungen**.
- **Hintergrund:** Der Immometrica-Scraper hatte bis v3.3-Fix eine Verifikations-Lücke: die Stat-Page wurde gelesen, bevor das neue Heading gerendert war → Werte der vorherigen Config wurden als aktuelle gelesen. Phase-B-Fix in `tools/portal-bewertung/portals/immometrica/portal.py::_wait_for_stat_heading` macht das clean (`status="stale_heading"` + uebersicht=null bei Heading-Mismatch). Die Quirk-Fallbacks in Modul 1 sind die zweite Verteidigungslinie für den Fall, dass der Scraper-Fix unerwartet versagt oder seltene Edge-Cases nicht abdeckt.

**Pflicht-Regeln:**

- **Alle Spalten linksbündig** (User-Vorgabe v3.2).
- **Bewertungs-Spalte ganz links** (User-Vorgabe v3.3 — User soll die Bewertung als erstes lesen, nicht die Rohwerte).
- Werte (€, €/m², Tage) **fettgedruckt**.
- Bewertungs-Spalte fusioniert Ampel + Prozent + Wort-Einordnung in EINE Zelle.
- **"Indikator:" statt "Verdikt:"** — bewusst neutrale Sprache, kein Lage-Urteil.
- Wort-Mapping skaliert mit gültigen Achsen (siehe Section 7.7 Aggregations-Logik).
- **Honesty-Disclaimer Pflicht** (siehe Section 7.7).
- **Stichproben-Warnung Pflicht** bei < 30 Inseraten je Achse.
- **Begriffe NICHT verwenden:** "Top-Stadtteil", "Schwacher Stadtteil", "Top-Nachfrage", "Liquidität", "Eichung", "Score 0–10".

#### Block 4 — ⚖️ Bewertung (Rename Verdikt → Bewertung seit v3.3)

```markdown
### ⚖️ Bewertung

**Ist-Gap:** <X,XX> % <Ampel>
**Ist-Abstand:** <X,XX> % <Ampel>
```

Nur die zwei Ist-Werte mit Ampel zeigen — keine Schwellen-Übersichts-Tabellen mehr (User-Wunsch v3.3: Schwellen-Bedeutung steht bereits in Section 7.7, doppelte Anzeige war redundant).

Berechnung `gap_ampel`:

`gap_prozent` ist positiv wenn Angebot ÜBER Konsens (schlecht), negativ wenn
Angebot UNTER Konsens (gut). Für die Lade-Darstellung wird
`gap_unter_konsens_prozent = -gap_prozent` gebildet (positive Zahl = Hebel
nach unten).

- `gap_unter_konsens_prozent ≥ 10` → `gap_ampel = "gruen"`
- `5 ≤ gap_unter_konsens_prozent < 10` → `gap_ampel = "gelb"`
- `gap_unter_konsens_prozent < 5` → `gap_ampel = "rot"`

Bei Angebot über Konsens ist die Zahl negativ — Anzeige Lese-richtig ("−3,5 %" =
Angebot liegt 3,5 % über Konsens), Ampel = rot.

Berechnung `marktpreis_ampel`:

```
preis_pro_qm_angebot = angebotspreis_eur / summe_wohnflaeche_qm
abstand_prozent = ((eur_per_qm.median - preis_pro_qm_angebot) / eur_per_qm.median) * 100
```

- `abstand_prozent ≥ 20` → `marktpreis_ampel = "gruen"`
- `15 ≤ abstand_prozent < 20` → `marktpreis_ampel = "gelb"`
- `abstand_prozent < 15` → `marktpreis_ampel = "rot"`

Wenn `eur_per_qm.median = null` oder `summe_wohnflaeche_qm` fehlt:
`marktpreis_ampel` wird **weggelassen** (Feld nicht in `modul_1` geschrieben —
Schema erlaubt nur `gruen|gelb|rot`, nicht `null`), und `Ist-Abstand` zeigt „—".

#### Block 5 — 🏠 Objektdaten & Risiken

```markdown
### 🏠 Objektdaten & Risiken

| Position | Wert |
|---|---|
| Anzahl WE | **<N>** |
| Ø Wohnungsgröße | **<X> m²** |
| Summe Wohnfläche | **<X> m²** |
| Baujahr | **<X>** |
| Energieklasse | **<X>** (<kWh/m²·a>) |
| Soll-Miete | **<X> €/Jahr** |
| IST-Miete | **<X> €/Jahr** oder **„Mietspiegel-Ableitung (Modul 5)"** |
```

**Wenn IST-Miete fehlt** (Leerstand / kein MV / kein Mietspiegel-Belegt):
NIE schätzen — Hinweis setzen, dass Modul 5 (Mietspiegel) den Wert nachliefert.
State-Feld: `modul_1.ist_miete_aus_mietspiegel = true`.

**Risiken (max 5 Zeilen, gekürzt)**:

```markdown
| # | Risiko | Ampel |
|---|---|:---:|
| 1 | <kurzer Text> | <Ampel> |
| 2 | … | … |
```

Risiken-Quellen (in dieser Priorität):
1. Baujahr < 1965 + Energieklasse F/G/H → 🔴 "Energetische Vollsanierung wahrscheinlich"
2. Leerstand ≥ 30% → 🟡 "Hoher Leerstand, Mietausfall-Risiko"
3. Keine Mietaufstellung gefunden → 🟡 "IST-Miete nicht belegt, Mietspiegel-Ableitung nötig"
4. Energieklasse H + WEG-Anteil ≥ 20 → 🔴 "WEG-Sanierungsbeschluss-Risiko (GEG §72)"
5. Gap-Ampel rot → 🟡 "Preisniveau knapp am Markt — Verhandlungs-Hebel klein"
6. Mehrere Mailings (Bundle ≥ 3) → 🟡 "Mehrere Makler bieten an — Marktstand prüfen"

Wenn keine Risiken erkennbar → Tabelle weglassen, Block 5 endet bei Objektdaten.

#### Block 6 — Abschluss

```markdown
**Vollanalyse (Modul 2: Objektbasis) starten?**
```

#### Verbindliche Regeln

- Block-Reihenfolge fest (Empfehlung zuerst, dann Score → Konsens → Verdikt → Objektdaten).
- Smileys 🟢🟡🔴 immer inline neben Status-Werten.
- Werte (€, €/m², %, m², Score, Baujahr, Energieklasse) **fettgedruckt**.
- Keine `=====`-Trennbalken — Blöcke durch Emoji-Überschriften + Leerzeile.
- Keine Maklerinfo, keine Annahmen-Liste, keine Audit-Spur (gehört in `.aufteiler/quickcheck-log.md`).
- Bei fehlenden Daten: „—" / „offen" / „Mietspiegel-Ableitung (Modul 5)" — niemals raten.

#### Persistenz

Dieses kompakte Block-Layout wird **zusätzlich** zum vollen Output-Block aus
10.1–10.7 geschrieben:

- Voller Output (10.1–10.7) → `<lead>/modul-1-output.md` + Terminal-Stream
- Kompaktes Block-Layout (10.8) → `<lead>/quickcheck.md` (User-facing Anker-Datei)

Beide werden parallel erzeugt. `quickcheck.md` ist die Datei, die der User
direkt im Lead-Ordner liest; `modul-1-output.md` ist die volle Datensicht für
Audit / spätere Module.

## 11. Akquise-Modus-Spezialitäten

Wenn `modus == "akquise"`:

### 11.1 Duplikat-Check (vor Schritt 2)

Aus altem Modul 0 Akquise-Modus Abschnitt A.5 unverändert übernehmen:
1. MD5-Hashes der eingegangenen PDFs berechnen
2. Bestehende `$AKQUISE_OBJEKTE_PATH` scannen
3. Bei Match: Mail-Ordner in existing Slug verschieben, `mail_queue.status=done`, `note='duplicate of <slug>'`, exit

### 11.2 Ordner-Rename

Nach Schritt 8/9 (objektdaten.json + state.json geschrieben):
1. Slug aus `adresse_volltext` ableiten (kebab-case, Umlaute ersetzt)
2. Ziel: `<onedrive>/Immobilien/001_AQUISE/Objekte/<slug>/`
3. Bei Duplikat-Pfad: `_2`, `_3` Suffix
4. `Move-Item _inbox/<msg-id>/ → Objekte/<slug>/`

### 11.3 Workspace-Datei

In `<slug>/<slug>.code-workspace` schreiben (Inhalt aus altem Modul 0 Abschnitt H unverändert).

### 11.4 Supabase-Inserts

Aus altem Akquise-Modus Abschnitt I unverändert:
- `POST /rest/v1/contacts` (Email-Upsert)
- `POST /rest/v1/deals` (mit `priority_score = scoring_gesamt × 10`, `preis_kauf`, `einheiten`, `wohnflaeche_m2`, etc.)
- `POST /rest/v1/activity_log`
- `PATCH /rest/v1/mail_queue?message_id=eq.<id>`

### 11.5 Markdown + €/m²-Tabelle

In `<slug>/quickcheck.md` (Backwards-Compat-Name) den Score-Overview-Block + Markt-Konsens + €/m²-Tabelle für Excel schreiben (unverändert aus altem Modul 0 Abschnitt G).

### 11.6 Audit-Log

`<slug>/quickcheck-log.md`: alle Roh-Eingaben, LLM-Antworten, Tool-Outputs, Defaults, Berechnungen — für Debugging.

### 11.7 Aufräumen

`.processing` NICHT selbst löschen — das macht der Watcher bei exit 0.

## 12. Übergabe-Statement

### 12.1 Orchestrator-Modus

```
Modul 0 (Datenbasis) abgeschlossen. Score: <X.X>/10 (<ampel>).
Gap: <X.X>% (<gap_ampel>).
objektdaten.json + modul_1 in state.json geschrieben.
Freigabe für Modul 1?
```

### 12.2 Akquise-Modus

```
Modul 0 (Akquise) fertig. Score: <X.X>/10. Lead-ID: <deal-id>.
Ordner: <pfad>. objektdaten.json + quickcheck.md geschrieben.
```

## 13. Self-Check (Pflicht vor Übergabe)

- [ ] `objektdaten.json` geschrieben und Schema-konform
- [ ] Alle Pflicht-Felder vorhanden + `wert != null`
- [ ] `we_liste.length == objekt.anzahl_we.wert`
- [ ] Σ `we_liste[].wohnflaeche_qm` ≈ `objekt.wohnflaeche_gesamt_qm` (±2%)
- [ ] Alle 8 `modernisierung_bestand`-Gewerke vorhanden (auch wenn `jahr=null`)
- [ ] `freitext_befunde[]` vorhanden (mind. 1 Eintrag ODER explizit leer mit Begründung in `meta.coverage_check`)
- [ ] `meta.coverage_check.second_pass_durchgeführt == true`
- [ ] `meta.coverage_check.stichproben_zitate.length >= 5`
- [ ] `markt.portale` mit min. 1 erfolgreichen Portal befüllt
- [ ] **(v2.1)** `markt.portale.immometrica.etw_verkauf` + `.miete` + `.mfh` + `.mfh_gap` befüllt (oder mit `null`-Werten + `meta.warnungen[]` bei Scraper-Fail)
- [ ] **(v2.1)** Deprecated-Aliase `markt.portale.immometrica.eur_pro_qm` / `.plz_median_eur_pro_qm` / `.stadt_median_eur_pro_qm` / `.vermarktungsdauer_median_tage` / `.inserate_anzahl_plz` synchron zu neuen Feldern
- [ ] **(v2.1)** `markt.gmb.lage_klassen` + `.objekt_einschaetzung` + `.marktdruck` befüllt (oder null bei fehlender Stadt-Page) + Deprecated-Alias `markt.gmb.eur_pro_qm` synchron
- [ ] **(v2.1)** `markt.eckdaten` mit Mietmultiplikator + Brutto-Rendite + KNK 12 % + Aufteilungs-Spread
- [ ] **(v2.1)** `markt.cashflow` mit Beleihung + Annuität + Ist + Soll + Mietsteigerungspotenzial
- [ ] **(v2.1)** `meta.daten_check` mit Vorhanden/Fehlend/Annahmen
- [ ] `scoring` mit 5 Sub-Scores + Gesamt-Score (alle 0–10) — Lage-Sub-Score 6-dim
- [ ] `state.json` mit `modul_1`-Block geschrieben
- [ ] **(v3.5)** `state.json.modul_1.pflicht_check` befüllt — `status` ∈ {`vollstaendig`, `unvollstaendig`}, `fehlend` Array mit Teilmenge aus {`energie`, `mieten`, `wohnflaeche`} (leer bei `vollstaendig`)
- [ ] **(v3.6 Akquise-Modus)** Schritt 9.5 (Q) gelaufen: bei `pflicht_status="unvollstaendig"` ⇒ `deals.status='offen'` gepatcht + `system_unterlagen_anfrage`-Notiz vorhanden (idempotent, max. 1 pro Deal pro 24h) mit `metadata.mailto_url` aus `makler-mail`-Skill
- [ ] **(v3.6 Akquise-Modus, Q.4 Re-Lauf)** Bei `pflicht_status="vollstaendig"` UND vorheriger `system_unterlagen_anfrage`-Notiz: genau eine `system_vollstaendig`-Erfolgsnotiz angehängt (`metadata.zuvor_fehlend` aus alter Notiz übernommen); alte Mangel-Notiz bleibt unverändert stehen
- [ ] `objekt.letzter_modul_lauf == "modul_1"`
- [ ] Output-Block (Daten-Check + Schnellkennzahlen + Cashflow + Markt-Vergleich + Sub-Markt + Lage-Sub-Score-Detail + Score-Overview) in `modul-0-output.md` erzeugt
- [ ] Validator-Lauf: `python tools/validate_objektdaten.py runs/<slug>/objektdaten.json` exit 0

Bei einem fehlgeschlagenen Check **außer** Recherche-Tool-Failures (die degradieren nur Konfidenz, kein Hard-Fail): state.json zurückrollen, exit != 0.

## 13.5 Ordner aufräumen (Pflicht — ganz am Ende, nach Self-Check)

Nachdem alle Dateien geschrieben + validiert sind, den Lead-Ordner in das
Soll-Layout bringen (siehe `docs/modul_0_ordnerstruktur.md`):

```bash
python tools/cleanup_lead_folder.py "<lead-ordner-pfad>"
```

Verschiebt Arbeits-/Zwischendateien (`modul-*-output.md`, `*.py`, Scraper-Dumps,
`quickcheck-log.md`) nach `.aufteiler/` und macht `Bilder/` sichtbar. **Bleiben im
Root:** `state.json`, `objektdaten.json`, `quickcheck.md`, `README.md` + die 4
Schlüssel-Dokumente (+ Excel/PDF ab Modul 6). Idempotent + OneDrive-Lock-robust —
bei Fehler nur Warnung, kein Hard-Fail (der Lead ist bereits vollständig analysiert).

## 14. Was Modul 0 NICHT macht

- Keine Excel-Befüllung (das macht Modul 5)
- Keine User-Fragen via AskUserQuestion (Modul 0 ist 100% automatisch)
- Keine Modul-1/2/3/4-Berechnungen (RND, Mietsubvention, etc. — das bleibt in den jeweiligen Modulen)
- Keine PDF-Generierung
- Bei Diskrepanz kritischer Felder kein Default-Wert wählen, sondern hart stoppen

## 15. Migrations-Historie

- **2026-06-04 (v3.7, ImmoCRM "% Markt"-Spalte — Schritt Q.0 Markt-€/m²-Sync):** Neuer Schritt **Q.0** am Anfang von Schritt 9.5 (CRM-Sync), direkt nach dem Modus-/ENV-Block und vor Q.1. Schreibt den Markt-Konsens-€/m² aus `state.json.modul_1.eur_per_qm.median` per PATCH nach `deals.markt_pro_m2`. Das ImmoCRM-Frontend (`LeadTable.tsx`, Spalte `markt_abweichung` "% Markt") rechnet daraus `(preis_pro_m2 − markt_pro_m2) / markt_pro_m2 × 100`. **Läuft immer** wenn `deal_id` vorhanden ist — unabhängig vom Pflicht-Check-Status (auch vollständige Leads brauchen den Markt-Wert). **Idempotent:** PATCH überschreibt dieselbe Spalte, kein Duplikat. Bei `eur_per_qm.median = null` (alle 4 Portale lieferten null) wird Q.0 bewusst übersprungen — kein Fehler, "% Markt"-Spalte bleibt leer. Wert wird auf 2 Nachkommastellen gerundet (numeric-Spalte). Self-Check (Q-Phase) um Q.0-Item erweitert. Hintergrund: CRM-Spalte + DB-Feld `deals.markt_pro_m2` (Migration 031) waren seit 2026-06-04 live, aber Modul 1 befüllte den Wert nicht — Spalte blieb leer. DB-seitig (Migration 031, View `deals_with_followup`) keine Änderung nötig, Spalte ist beschreibbar (nicht GENERATED). Siehe Memory `immocrm-markt-prozent-spalte` + `modul-0-portal-konsens`.
- **2026-05-27 (v3.6, Sub-Plan 6 ImmoCRM — Schritt Q CRM-Sync + Re-Lauf-Erfolgs-Notiz):** Neuer Schritt 9.5 "CRM-Sync (Schritt Q)" zwischen Schritt 9 (State-Write) und Schritt 10 (Output-Block) — läuft nur im Akquise-Modus (wenn `state.json.modul_1.deal_id` gesetzt). **Q.1 Status-PATCH:** Bei `pflicht_check.status="unvollstaendig"` patcht Modul 1 selbst `deals.status='offen'` per Supabase REST (Owner-Entscheidung 2026-05-27: Status **immer** auf "offen" bei Lücke, auch wenn vorher manuell auf "berechnet"). **Q.2 makler-mail-Aufruf:** ruft `makler-mail`-Skill mit `unterlagen-anfrage --non-interactive=true` und Mängelliste auf Deutsch (Mapping `energie` → "Energieausweis bzw. Energieeffizienzklasse", `mieten` → "Mietaufstellung (Anzahl Wohnungen + Kaltmieten)", `wohnflaeche` → "Wohnfläche in m²"). Skill gibt nur Plain-Text-`MAILTO_URL=...`-Zeile zurück. **Q.3 Notiz-Insert (idempotent):** Vor-Check via REST-Query — existiert in den letzten 24h schon eine ungelesene `system_unterlagen_anfrage`-Notiz für diesen Deal, wird sie per PATCH mit aktueller `mailto_url`/`content_html` aktualisiert statt eine zweite Notiz anzulegen; sonst POST mit `kind=system_unterlagen_anfrage`, `metadata.{fehlende_pflichtdaten, mailto_url, empfaenger_name, empfaenger_email}`, `read_at=null`. **Q.4 Re-Lauf-Erkennung:** Bei `pflicht_status="vollstaendig"` Lookup auf alte `system_unterlagen_anfrage`-Notizen. Wenn welche existieren → ein neuer `system_vollstaendig`-Eintrag wird angehängt mit `metadata.zuvor_fehlend` (übernommen aus der jüngsten alten Mangel-Notiz) und `read_at=null`. Erst-Lauf ohne Mangel-Vorgeschichte schreibt **keine** Vollständig-Notiz (kein Lärm). Alte Mangel-Notizen bleiben als Audit-Spur unverändert; Lead-Status wird in Q.4 nicht automatisch zurückgesetzt. Schluss-Absatz von Schritt 8.5/P entsprechend umformuliert ("Modul 1 macht CRM-Sync selbst"), Self-Check (Section 13) um zwei Q-Items erweitert. Plan: `ImmoCRM/docs/superpowers/plans/2026-05-27-modul1-pflicht-check-und-unterlagen-workflow.md` Task 11 + 13. Voraussetzung Task 12: `makler-mail`-Skill versteht `--non-interactive=true` ab v1.1 (kein Outlook-Öffnen, kein AskUserQuestion, gibt nur `MAILTO_URL=...`-Plain-Text zurück).
- **2026-05-27 (v3.5, Sub-Plan 6 ImmoCRM — Pflicht-Check + Hard-Fail-Entschärfung):** Modul 1 bricht nicht mehr bei fehlenden Pflicht-Dateien (Exposé / Mieterliste / Modernisierungsliste) hart ab. Schritt 1.4 ("Pflicht-Check HARD FAIL") umgewandelt zu "Pflicht-Daten-Markierung" — fehlende Klassen landen in `meta.warnungen[]`, Skill läuft weiter. Schritt 4 ("Pflicht-Feld-Validierung HARD FAIL") analog entschärft — Lücken landen in `meta.daten_check.fehlend[]`. Einziger weiterhin geltender Hard-Fail: Ordner nicht lesbar / komplett leerer Ordner. Bei fehlender Adresse + Slug `unbekannt - <msg-id-short>` schreibt Modul 1 trotzdem state.json mit `pflicht_check.fehlend=["adresse", ...]` und exit 0. **Neuer Schritt 8.5 "Pflicht-Check (Schritt P)"** zwischen Schritt 8 (`objektdaten.json` schreiben) und Schritt 9 (State-Init). Prüft drei harte Pflicht-Felder auf den extrahierten Objektdaten: (1) **Energie** = `energieausweis.klasse.wert` gesetzt+≠"unbekannt" ODER `energieausweis.kennwert_kwh_qm_a.wert` gesetzt; (2) **Mieten** = mindestens 1 `we_liste[*].ist_miete_eur_monat.wert` gesetzt (Alias-Pfad `kaltmiete_eur` für ältere Files); (3) **Wohnfläche** = `objekt.wohnflaeche_gesamt_qm.wert` > 0 ODER Σ `we_liste[*].wohnflaeche_qm.wert` > 0. Schreibt Ergebnis nach `state.json.modul_1.pflicht_check = {status, fehlend[]}` (Schema-Erweiterung in `docs/state.schema.json`). Modul 0 (Schritt L.1) liest diesen Block und entscheidet über CRM-Lead-Status + Unterlagen-Anfrage-Notiz. Self-Check (Section 13) um pflicht_check-Item erweitert. Plan: `ImmoCRM/docs/superpowers/plans/2026-05-27-modul1-pflicht-check-und-unterlagen-workflow.md` Task 10. Owner-Begründung: Lead darf trotz fehlender Unterlagen nicht im Watcher verschwinden — er gehört ins CRM mit Status `offen` und einer Mail-Vorlage an den Makler.
- **2026-05-27 (v3.4):** Energie- und Mietpotenzial-Sub-Score neu kalibriert (User-Vorgabe).
  **Energie:** Drei Stützpunkte C=10, D=9, H=1 (User-Vorgabe), dazwischen linear
  (E=7, F=5, G=3). Klassen besser als C werden bei 10 gecappt (A+/A/B = 10).
  Hintergrund: User-Logik "C ist schon Top im NRW-Bestand → voller Score; alles
  schlechter als C wird gleichmäßig abgewertet, H ist nur knapp über null statt
  hart null". Sections 7.3 / 10.6 / 10.8 Block 2 entsprechend angepasst.
  **Miet-Potenzial:** (a) Ziel-Miete neu = Mietspiegel-Obergrenze (§558-Maximum,
  legaler Hebel auf Bestandsmieter) mit Markt-Median PLZ (Immometrica) als
  Fallback bei Mietspiegel-DB-Lücke. (b) Skalierung von `/10` auf `/5` →
  Cap-Punkt bei 50 % Hebepotenzial statt 100 %. Heißt: 10 % → 2 P, 25 % → 5 P,
  40 % → 8 P, 50 %+ → 10 P. Hintergrund: 50 % Hebel ist bei Bestandsobjekten
  bereits außergewöhnlicher Aufteiler-Deal, höhere Werte meist Rechen-Artefakt
  aus extrem niedrigen Alt-Mieten. (c) Neue State-Felder
  `scoring.miet_potenzial.{ziel_eur_pro_qm, ziel_quelle, ist_schnitt_eur_pro_qm,
  potenzial_prozent}` für Nachvollziehbarkeit. (d) Audit-Block (10.6) und
  quickcheck.md-Block (10.8 Block 2) zeigen Ziel-Miete + Hebel absolut
  (€/Jahr Mehr-Kaltmiete bei voller Ausschöpfung).
- **2026-05-26 (v3.3):** Stadtteil-Vergleich auf **5 Achsen** erweitert — neue Achse 5 "Aufteilungs-Premium PLZ" aus `markt.portale.immometrica.mfh_gap.gap_prozent` (invertiert zu positivem Premium-Wert: `-gap_prozent`). Schwellen: 🟢 ≥ +15 % / 🟡 +5–15 % / 🔴 < +5 %. Wort-Mapping: "starker / solider / moderater / kaum / kein Spread". **Dreischichtiger Robustheits-Check** gegen Scraper-Quirks: (1) `mfh.plz == etw_verkauf.plz` → `caveat="tool_quirk_mfh_eq_etw"`, (2) `mfh.plz < 200 €/m²` (Miete-Wert geleckt) → `caveat="tool_quirk_miete_leck"`, (3) `mfh.plz.inserate_anzahl < 3` → `caveat="zu_wenig_inserate"`. Alle drei führen zu `ampel="nv"` und Skip im Aggregations-Zähler. Adaptive Schwellen: m=5: ≥4🟢; m=4: ≥3🟢. **Spalten-Reorder** Block 3.5: Bewertung jetzt ganz links. **Block 4 Rename** "⚖️ Verdikt" → "⚖️ Bewertung". **Schwellen-Übersichts-Tabellen** in Block 4 entfernt. **Begleitender Scraper-Fix (separate Datei):** `tools/portal-bewertung/portals/immometrica/portal.py` bekam einen heading-basierten Diff-Check (`_wait_for_stat_heading`, neue Konstante `_RADIO_TO_EXPECTED_HEADING`). Hintergrund: Diagnose-Lauf 2026-05-26 zeigte, dass bei allen drei Test-Leads (Klingelpoth/Essen/Dortmund) 3-5 von 6 Configs jeweils falsche Werte lieferten — die Stat-Page wurde gelesen, bevor das neue Heading nach Submit gerendert war, der Parser las die Werte der vorherigen Config. Der Heading-Check wartet nun explizit darauf, dass `Übersicht:`-heading zum gewünschten Radio-Label passt; bei Mismatch wird `status="stale_heading"` gesetzt und `uebersicht/zusatzinfo=null` zurückgegeben, sodass Konsumenten keine falschen Werte lesen können. Die Caveat-Logik in Modul 1 bleibt als zweite Verteidigungslinie aktiv.
- **2026-05-26 (v3.2):** Stadtteil-Vergleichs-Tabelle als 4-Achsen-**Markt-Indikator** + Bewertungs-Spalte — eingeführt nach Klingelpoth-Re-Run-Feedback ("Wir reden immer von der Stadt, niemals vom Kreis" + "Nackte €/m²-Werte muss ich nicht selbst einordnen können"). Neue Sections: (a) **5.7** PLZ + Stadt-Einwohner-Lookup als optionaler Helper (`tools/plz_einwohner_lookup.py` + CSV-Cache), (b) **7.7** Stadtteil-Vergleich-Berechnung mit **4 Achsen** (Verkaufspreis €/m², Mietpreis €/m²/Mo, Vermarktungsdauer Verkauf, Vermarktungsdauer Vermietung) + Indikator-Logik (3-4🟢 = "PLZ über Stadt-Schnitt", 2🟢 = "PLZ um Stadt-Schnitt", 0-1🟢 = "PLZ unter Stadt-Schnitt"), (c) **10.8 Block 3.5** Pflicht-Block in `quickcheck.md` (linksbündig, fusionierte Bewertungs-Spalte). **Modell-Honesty:** Markt-Vergleichs-Indikator ersetzt KEIN Lage-Urteil — Disclaimer + Stichproben-Warnung Pflicht. Begriffe "Top-Stadtteil", "Top-Nachfrage", "Liquidität", "Eichung", "Score 0–10" sind im User-Output **verboten** — zu suggestiv oder zu technokratisch. **Verworfene Achse:** "Anzeigen pro 1.000 EW / Monat" wurde initial geplant, nach Sanity-Check (4 Referenz-PLZ Düsseldorf-Bilk + Köln-Eigelstein + Dortmund-Nordstadt + Soest) verworfen — misst Mieter-Fluktuation, nicht Lage-Qualität (Korrelation gegenteilig zur Hypothese). Doku: `docs/anzeigen-pro-ew-sanity-check.md`.
- **2026-05-26 (v3.1):** Pflicht-Ausformulierung der Sub-Score-Begründungen — eingeführt nach Klingelpoth-Re-Run-Feedback ("PLZ +7%" ist kein Audit-Text). Drei Blöcke betroffen: (a) Section 10.6 Lage-Sub-Score-Detail mit Pflicht-Format pro k1–k6 (PLZ + Stadt absolut, Premium %, Formel mit Zwischenwert, Lese-Sinn-Satz, Gewicht), (b) Section 10.7 mit obligatorischem "BEGRÜNDUNGEN PRO SUB-SCORE"-Block direkt nach dem ASCII-Score-Overview (Miete-Potenzial, Energie, Zustand, Deal-Gap jeweils mit Quellen + Berechnung + Lese-Sinn), (c) Section 10.8 Block 2 mit ausformulierten Sub-Score-Blöcken in `quickcheck.md` statt einer Kurz-Tabelle. Begründung: User muss aus den Output-Files heraus — ohne in `objektdaten.json` schauen zu müssen — verstehen können worauf jede Prozentzahl sich bezieht, woher sie kommt, und wie sie zum Score wird.
- **2026-05-26 (v3.0):** Refactor — Skill umbenannt von `aufteiler-modul-0-datenbasis` (v2.1) zu `aufteiler-modul-1-auto-analyse`. CRM-Akquise-Pipeline ausgelagert in neuen Skill `aufteiler-modul-0-akquise-automatisierung`. Block-Layout-Output (Abschnitt 10.8, `quickcheck.md`) aus ex-quickcheck-Hybrid integriert. State-Schema 2.0 — Modul-Block heißt jetzt `modul_1` (vorher `modul_0` in v2.1 → v1.0-State). Bestehende v1.0-State-Files bleiben gültig via `docs/state.schema.v1.json` (Backwards-Compat).
- **2026-05-22 (v2.1):** Markt-KPIs PLZ vs. Stadt + Cashflow-Block + 6-dim Lage-Sub-Score.
- **2026-05-21 (v2.0):** Initial-Refactor — `aufteiler-modul-0-datenbasis` ersetzte alten `aufteiler-modul-0-quickcheck` (Hybrid) im Orchestrator-Pfad. Holistische PDF-Extraktion, 5-Sub-Score, Portal-Pipeline.

## Referenzen

- Schema: `docs/objektdaten-schema.md`
- Excel-Mapping: `docs/excel_handoff.md`
- Refactor-Log: `plans/2026-05-21-refactor-implementierungs-log.md`
- Markt-KPIs + Cashflow Plan (v2.1): `plans/2026-05-22-modul0-marktkpis-cashflow.md`
- BORIS-Scraper: `tools/m01_boris_brw.py`
- Portal-Pipeline: `tools/portal-bewertung/m00_portal_pricer.py`
- Notion-DBs:
  - GMB: `3310ae59-38e4-81f1-ad36-e8bd809d437a`
  - Mietspiegel NRW: `8b000923-d5ee-45a4-8f6a-e7f3bf81f20e`

---

## Versions-Historie

- **v2.0 (2026-05-21):** Initial Refactor — holistische PDF-Extraktion, 5-Sub-Score, Portal-Pipeline
- **v2.1 (2026-05-22):** Markt-KPIs + Cashflow + Coach-Expertise
  - Immometrica-Output erweitert auf 6 Configs (Verkauf-PLZ/Stadt, Miete-PLZ/Stadt, MFH-PLZ/Stadt) inkl. dimensionaler Sub-Charts (Zimmer/Wohnfläche/Baujahr)
  - GMB-Lookup erweitert: Lage-Klassen (gut/mittel/mäßig), Marktdruck, BRW-Spanne MFH; automatische Objekt-Einschätzung
  - Lage-Sub-Score von 2-dim auf **6-dim Variante B** (k1–k6, gewichtet) — inkl. GMB-Lage-Klasse als k6
  - Eckdaten-Block: Mietmultiplikator, Brutto-Rendite, NRW-KNK 12 %, Aufteilungs-Spread (Faktor 14 × Soll-Kaltmiete)
  - Cashflow-Block: 80 % Beleihung, 6 % Annuität, 20 % BWK-Pauschale, Cashflow-Rendite EK Ist + Soll, Mietsteigerungspotenzial
  - Output-Block neu strukturiert: Daten-Check → Schnellkennzahlen → Cashflow → Markt-Vergleich PLZ vs. Stadt → Sub-Markt (Vermarktungsdauer pro WE-Typ) → Lage-Sub-Score-Detail → Score-Overview (bisher)
- **v3.0 (2026-05-26):** Rename + Block-Layout-Integration (siehe Migrations-Historie oben)
- **v3.1 (2026-05-26):** Pflicht-Ausformulierung Sub-Score-Begründungen (Sections 10.6 / 10.7 / 10.8 Block 2) — User-Audit-Anker für jede Score-Zahl mit Bezugsgröße, Formel, Quelle, Lese-Sinn
- **v3.2 (2026-05-26):** Stadtteil-Vergleich als 4-Achsen-Markt-Indikator + Bewertungs-Spalte (Sections 5.7 / 7.7 / 10.8 Block 3.5) — bewusst neutraler "Indikator" statt "Verdikt", Honesty-Disclaimer + Stichproben-Warnung Pflicht. Anzeigen-pro-EW-Achse nach Sanity-Check verworfen.
- **v3.3 (2026-05-26):** 5. Achse "Aufteilungs-Premium PLZ" im Stadtteil-Vergleich (Sections 7.7 / 10.8 Block 3.5) aus `mfh_gap.gap_prozent` invertiert als Premium. Spalten-Reorder Block 3.5 — Bewertung ganz links. Block 4 "⚖️ Verdikt" → "⚖️ Bewertung", Schwellen-Übersichts-Tabellen entfernt. Robustheits-Fallback `n/v` mit "Tool-Quirk" / "zu wenig Inserate" macht die Achse gegen Scraper-MFH-Lecks immun.
- **v3.4 (2026-05-27):** Energie- und Mietpotenzial-Sub-Score neu kalibriert. Energie: Stützpunkte C=10 · D=9 · H=1 (linear interpoliert, A+/A/B bei 10 gecappt). Mietpotenzial: Ziel-Kaskade Mietspiegel-Obergrenze → Markt-Median-PLZ-Fallback, Cap-Punkt bei 50 % Hebel (statt 100 %), neue State-Felder `scoring.miet_potenzial.{ziel_eur_pro_qm, ziel_quelle, ist_schnitt_eur_pro_qm, potenzial_prozent}`, Audit-Blöcke 10.6 + 10.8 mit Hebel absolut in €/Jahr.
- **v3.5 (2026-05-27):** Sub-Plan 6 ImmoCRM — Schritt P (Pflicht-Check) + Hard-Fail-Entschärfung. Neuer Schritt 8.5 prüft Energie/Mieten/Wohnfläche auf `objektdaten.json`, schreibt `state.json.modul_1.pflicht_check`. Schritt 1.4 + Schritt 4 entschärft — Modul 1 läuft auch bei fehlenden Pflicht-Dateien durch, nur noch Hard-Fail bei nicht lesbarem Ordner oder Adress-Fallback `unbekannt - <msg-id-short>`.
- **v3.6 (2026-05-27):** Sub-Plan 6 ImmoCRM — Schritt Q (CRM-Sync, Q.1–Q.4). Neuer Schritt 9.5 macht im Akquise-Modus: Q.1 `deals.status='offen'` bei Lücke, Q.2 `makler-mail`-Skill non-interactive für Mailto-URL, Q.3 idempotenter `deal_notes`-Insert (max. 1 ungelesene `system_unterlagen_anfrage`-Notiz pro Deal pro 24h — sonst PATCH), Q.4 `system_vollstaendig`-Erfolgs-Notiz bei Re-Lauf mit nun vollständigen Daten (nur wenn vorhin Mangel-Notiz existierte). Voraussetzung: `makler-mail`-Skill v1.1+ mit `--non-interactive=true`-Modus.
- **v3.7 (2026-06-04):** Schritt Q.0 — Markt-Konsens-€/m² (`eur_per_qm.median`) per PATCH nach `deals.markt_pro_m2` für die ImmoCRM-"% Markt"-Spalte. Läuft immer (unabhängig vom Pflicht-Status), idempotent, Skip bei `median=null`. Self-Check um Q.0-Item erweitert.
