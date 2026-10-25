---
name: aufteiler-modul-4-massnahmen
description: Modul 4 der Aufteiler-Analyse — Sanierungs-/Modernisierungskosten inkl. RND-Gutachten und WEG-Teilung als Reno-Positionen. Wird ausschließlich vom aufteiler-Orchestrator aufgerufen. Seit 2026-06-11 Pflicht-Visualisierung des kompletten Zonen-Outputs + Excel-Transfer-Vorschau im Chat vor dem Orchestrator-Gate; Entscheidungs-Weichen > ±5 % (Massnahmen-Kosten, WEG-Kosten) nie autonom auflösen.
---

# Modul 3 — Massnahmen

Sanierungs- und Modernisierungskosten je Gewerk, plus zwei Pflicht-Positionen RND-Gutachten und WEG-Teilung. Energetische Massnahmen-Wirkung (Klassen-Sprünge G→F, F→E, …) aus Notion-DB EnEV. Asset-Trennung enforced: **keine** Mietsubvention/Rücklage in `massnahmen_liste` — die gehören nach Modul 4 bzw. in die VERKAUFSMATRIX-Extra-Spalten.

## 1. State laden (Pflicht — erste Aktion)

1. Vom Orchestrator bekomme ich `objekt_slug`. Pfad: `runs/<objekt_slug>/state.json`.
2. State einlesen mit `Read`.
3. Pflicht-Vorgänger-Felder prüfen. Wenn etwas fehlt → STOPP, Antwort an Orchestrator:
   `"Modul 3: Pflichtfeld <pfad> fehlt. Bitte Modul <M> erneut laufen lassen."`

**Pflicht-Vorgänger:**
- `modul_2.we_liste` (Anzahl + Wohnflächen für WE-Renovierung)
- `modul_3.rnd_jahre` und `modul_3.rnd_frozen === true` (RND darf hier NICHT verändert werden)

Wenn `modul_3.rnd_frozen !== true` → STOPP: `"Modul 3: Modul 3 nicht abgeschlossen (rnd_frozen fehlt). Bitte Modul 3 erneut laufen lassen."`

## 1a. Entscheidungs-Weichen während des Modullaufs (Pflicht-Regel)

Trifft das Modul auf eine echte Weiche — eine Annahme-Entscheidung mit Effekt > ±5 % auf ein Modul-Ergebnis (Mod-Summe, Gesamtinvestition) — SOFORT `AskUserQuestion` stellen, mit der eigenen Empfehlung als erster Option (Suffix „(Empfehlung)"). Solche Weichen NIE autonom mit der eigenen Empfehlung auflösen — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

Typische Weichen in diesem Modul:
- Massnahmen-Auswahl + Kostenhöhe je Gewerk, wenn keine User-Werte vorliegen und die Heuristik-Korridore (z.B. Fassade WDVS 250–300 €/m²) die Mod-Summe > ±5 % spreizen
- WEG-Teilungs-Kosten (Default-Vorschlag 15.000 € — bereits User-Frage, bleibt)
- Leerstand-Anzahl, wenn Exposé-Suche kein eindeutiges Ergebnis liefert (bereits `AskUserQuestion` in 2a-PRE, bleibt)
- WE-Reno-Stufe 350 vs. 450 €/m² (mit/ohne Elektrik komplett), wenn der Elektrik-Zustand unklar ist
- Nebenkosten-Quote abweichend vom 10 %-Default (z.B. Architekt/Statik absehbar teurer)

Ohne Weichen läuft das Modul autonom durch — endet aber IMMER in der Pflicht-Visualisierung (Sektion 7) + dem Freigabe-Gate des Orchestrators.

## 2. Inputs erheben

**2a) Brutto/Netto-Konvention (VERBINDLICH):**

Modul 3 liefert **immer Netto-Werte** in `modul_4.massnahmen_liste[].kosten_netto_eur` sowie `modul_4.rnd_gutachten_netto_eur` und `modul_4.weg_teilung_netto_eur`. Die Excel `RENO`-Tabelle rechnet die 19 % USt automatisch via `RENO!I7 = 0.19` auf alle Positionen hoch — Modul 3 muss nichts brutto liefern.

**Wenn der User einen Brutto-Preis nennt** (z.B. „Gutachter kostet 1.190 € brutto/WE" oder „WEG-Teilung 17.850 € brutto"): vor dem State-Write **rückrechnen**:
```
kosten_netto_eur = kosten_brutto_eur / 1.19
```

Konkrete Default-Annahmen:
- **RND-Gutachten:** 600 €/WE **netto** (= 714 € brutto/WE über RENO-USt). Seit 2026-06-15 (vorher 1.000 €/WE). Landet in RENO Zeile 105 (`RND`).
- **WEG-Teilung:** Excel-Template Default `RENO!K104 = 12.000 €/Stk netto`. Wenn User abweicht, immer netto liefern.

**2a-PRE) Leerstand ermitteln — PFLICHTSCHRITT vor allen anderen Inputs:**

WE-Renovierung gilt NUR für leerstehende WE. Vermietete WE werden nicht angefasst.

1. Lies `state.json` → `modul_4.leerstand_we_anzahl` falls bereits vorhanden.
2. Suche im Exposé-Text (`web-expose.html`, `body.txt`, `modul-0-output.md`) nach:
   `"Neuvermietung"`, `"leer"`, `"Leerstand"`, `"unvermietet"`, `"frei"`, `"vakant"`
3. Falls Treffer: `leerstand_we_anzahl = N` ableiten, Quelle dokumentieren.
4. Falls kein Treffer: `AskUserQuestion`:
   > "Wie viele WE stehen bei Übernahme leer / werden renovierbar frei? (0 = alle vermietet)"
   Optionen: 0, 1, 2, 3, 4+
5. `leerstand_wohnflaeche_qm = Σ wohnflaeche_qm der leerstehenden WE aus modul_2.we_liste`
   Falls Einzel-WE unbekannt: `leerstand_we_anzahl × modul_1.avg_we_groesse_qm`

**NIEMALS annehmen, dass alle WE renoviert werden.**
Bei `leerstand_we_anzahl == 0`: kein WE-Reno-Eintrag in massnahmen_liste.

**2b) Massnahmen pro Kategorie abfragen (eine `AskUserQuestion`):**

Acht Kategorien (Schema-Enum `modul_4.massnahmen_liste[].kategorie`):
1. `Dach`
2. `Fassade`
3. `Fenster`
4. `Heizung`
5. `Elektrik`
6. `Sanitaer`
7. `Boeden`
8. `Grundriss`
9. `Sonstiges` (Reserve)

Pro Kategorie eine User-Frage:
> `<Kategorie>: Welche Massnahme geplant 2026? Format: <Ist-Zustand> | <Geplant> | <Kosten netto €>. Mehrere Zeilen erlaubt. 'keine' wenn nichts geplant.`

Beispiel-Antwort:
```
Dach: Eindeckung 1978, undicht | WDVS + Neueindeckung | 38000
Fassade: keine
Fenster: 2-fach 1995 | 3-fach Wärmeschutz | 22000
```

**2c) Pflicht-Positionen (automatisch ergänzen, keine User-Frage):**

- **RND-Gutachten**: `rnd_gutachten_netto_eur = 600 × len(modul_2.we_liste)` (600 €/WE pauschal). Eintrag in `massnahmen_liste` als `kategorie="Sonstiges"`, `ist_zustand="—"`, `geplant="RND-Gutachten (600 EUR/WE)"`, `kosten_netto_eur=<Summe>`. Modul 6 schreibt das nach RENO Zeile 105 (`RND`, K105=600, I105=N).
- **WEG-Teilung**: User-Frage mit Default-Vorschlag 15.000 € (NRW-Erfahrungswert für 1 Haus). Eintrag als `kategorie="Sonstiges"`, `ist_zustand="—"`, `geplant="WEG-Teilung Einmalkosten"`, `kosten_netto_eur=<Wert>`.

**2d) Asset-Trennung (Pflicht-Check vor State-Write):**

Weder `kategorie` noch `ist_zustand` noch `geplant` darf das Wort `subvention`, `rücklage` oder `ruecklage` enthalten (case-insensitive Substring-Match). Validator enforced das ohnehin, aber das Modul muss explizit darauf prüfen und User-freundlich abweisen, bevor State geschrieben wird.

**2e) Optional — Energieklasse:**

Falls Energieausweis vorhanden, abfragen: `enev_klasse` aus Enum `A+, A, B, C, D, E, F, G, H, unbekannt`. Default: `unbekannt`.

## 3. Berechnung / Logik

**3a) Tiefenstufen-Wahl:**

| Stufe | Eingang vorhanden | Output |
|-------|-------------------|--------|
| 1 | Adresse + WE-Liste | Pauschale Standard-Annahmen pro Kategorie (z.B. 350 €/m² WE-Reno) |
| 2 | + Bestand-Modernisierungsstand (aus Modul 2) | Zustands-Bewertung je Gewerk, gezielte Kosten |
| 3 | + Mod-Score aus M2 + Energieklasse | Korrigierte Kostenschätzung, EnEV-Massnahmen aus Notion-DB |
| 4 | + partielle Handwerker-Angebote | Eingerechnete Ist-Werte |
| 5 | + voll dokumentierte Massnahmen (Angebote pro Gewerk) | Pixel-genaue Reno-Tabelle |

`tiefenstufe` 1–5, Schema-Max 5. Default-Ziel: Stufe 2.

**3b) Kosten-Heuristiken (Default Stufe 1–3, wenn keine konkreten Werte vom User):**

Aus altem XML (Modul 2 v1.3):
- **WE-Renovierung Basis** (Böden, Wände, Decken, Türen, Bad-Refresh, Lichtschalter): `350 €/m² × leerstand_wohnflaeche_qm` — NUR leerstehende WE, nie alle WE pauschal
- **WE-Renovierung mit Elektrik komplett neu**: `450 €/m² × leerstand_wohnflaeche_qm`
- **WEG-Teilung pauschal pro Haus**: `15.000 €` (Notar Teilungserklärung, Grundbuch, Aufteilungsplan, Abgeschlossenheitsbescheinigung)
- **Energetische Massnahmen** (Dach, Fassade WDVS, Fenster, Heizungstausch): aus Notion-DB EnEV `Kosten €/m² WF` × Σ Wohnfläche, falls verfügbar; sonst Default-Korridor pro Bauteil (Dach 80–120 €/m² WF, Fassade WDVS 250–300 €/m² WF, Fenster 600–800 €/Stk, Heizung 15.000–25.000 € pro Haus).

User-Werte haben immer Vorrang vor Heuristiken.

**3c) Summen berechnen:**

```
modernisierung_netto_eur = Σ kosten_netto_eur über alle massnahmen_liste-Einträge
modernisierung_brutto_eur = modernisierung_netto_eur × 1.19   # USt 19 %

nebenkosten_netto_eur = modernisierung_netto_eur × 0.10        # Default 10 % Nebenkosten (Architekt, Statik, Genehmigung)
nebenkosten_brutto_eur = nebenkosten_netto_eur × 1.19
```

**3d) Kernsanierung-Flag:**

`ist_kernsanierung = (modernisierung_netto_eur > kaufpreis_eur × 0.5) OR (mod_score >= 18 AND viele Gewerke mit Aufteiler-Massnahme)`

Konkret: User kann beim Massnahmen-Erheben „Kernsanierung ja/nein" mit-angeben. Default: Modul leitet aus Kosten-Quote ab. Wenn `ist_kernsanierung=true`: Hinweis in Zone C, Modul 2 hatte ggf. schon 90 %-Cap angewendet.

**3e) Plausibilitäts-Prüfung:**

- `modernisierung_netto_eur > 0` (mindestens RND-Gutachten + WEG ergibt > 0).
- Plausi-Warnung wenn `modernisierung_netto_eur > modul_1.angebotspreis_eur` (mehr Reno als Kaufpreis → außergewöhnlich, in Zone C ausweisen).
- Asset-Trennung: keine `subvention`/`rücklage`/`ruecklage` in `massnahmen_liste`-Texten (Validator enforced).

## 4. Output erzeugen (Drei Zonen)

**Zone A — Daten-Block (pixel-identisch über alle Objekte):**

Block 1 — Massnahmen-Tabelle:
```
| Nr | Kategorie | Ist-Zustand                  | Geplant                       | Kosten netto € | Kosten brutto € |
|----|-----------|------------------------------|-------------------------------|----------------|-----------------|
| 1  | Dach      | Eindeckung 1978, undicht     | WDVS + Neueindeckung          | 38.000         | 45.220          |
| 2  | Fenster   | 2-fach 1995                  | 3-fach Wärmeschutz            | 22.000         | 26.180          |
| …  | …         | …                            | …                             | …              | …               |
| N-1| Sonstiges | —                            | RND-Gutachten (600 EUR/WE)  | <X>            | <X×1.19>        |
| N  | Sonstiges | —                            | WEG-Teilung Einmalkosten      | 15.000         | 17.850          |
| Σ  |           |                              |                               | <Σ netto>      | <Σ brutto>      |
```

Block 2 — Summen + Nebenkosten:
```
| Position                          | Netto €    | Brutto €   |
|-----------------------------------|------------|------------|
| Modernisierung Summe              | <Σ netto>  | <Σ brutto> |
| Nebenkosten (10 % von Mod.)       | <NK netto> | <NK brutto>|
| Gesamtinvestition                 | <ges netto>| <ges brutto>|
```

Block 3 — Eckdaten:
```
| Parameter                | Wert                              |
|--------------------------|-----------------------------------|
| Anzahl WE (aus Modul 1)  | <N>                               |
| RND-Gutachten netto      | <600 × N> €                      |
| WEG-Teilung netto        | <Wert> €                          |
| Energieklasse Ist        | <A+..H / unbekannt>               |
| Kernsanierung-Flag       | ja / nein                         |
| Asset-Trennung-Check     | ok                                |
```

Nicht-ermittelbare Werte: `"n/a"`, nicht weglassen.

**Zone B:**
```
Tiefenstufe: <N> von 5 (<Begründung wenn nicht 5>)
Konfidenz: <hoch|mittel|niedrig>
```

**Zone C:**

1. **Wichtigste Annahmen** (max 5 Bullets) — z.B. „WE-Reno Basis 350 €/m² als Default-Heuristik", „EnEV-Klassensprung F→D durch Dach + Fassade".
2. **Risiken / Unsicherheiten** (max 5 Bullets) — z.B. „Heizung-Kosten geschätzt, Angebot fehlt", „Brutto/Netto-Excel-Verifikation noch offen — beide Summen geliefert".
3. **Empfehlung** (1–3 Sätze) — z.B. „Vor Modul 5: Heizung + Fassade Handwerker-Angebote holen, Stufe 4 erreichen."

**Excel-Transfer-Vorschau (Pflicht-Block nach Zone C):**

Tabelle der Zellen, die die Werte DIESES Moduls später (physischer Write erst in Modul 6 nach separater Freigabe) befüllen — Zell-Verträge aus `docs/excel_handoff.md`:

```
| Sheet!Zelle                  | Wert                                         |
|------------------------------|----------------------------------------------|
| RENO!I<zeile> je Massnahme   | <Menge> (Kategorie→Zeilen-Mapping handoff.md)|
| RENO!I104                    | 1 (WEG-Teilung aktiv)                        |
| RENO!K104                    | <weg_teilung_netto_eur, nur wenn ≠ 12.000>   |
| BESICHTIGUNG!B18..B23        | <Zustands-Texte Dach/Fassade/Fenster/SP/Heizung/Elektrik> |
| KALKU!E35/E37/E38/E39 (opt.) | <Heizungsart / Fassade gedämmt / Zählerschrank / Treppenhaus> |
```

(RND-Gutachten → RENO Zeile 105 (`RND`, 600 €/WE × Anzahl WE) via Modul 6. Mietsubvention gehört zu Modul 5 → VERKAUFSMATRIX!Y27 (negativ), NICHT hierher — Asset-Trennung.)

## 5. State persistieren

1. `modul_4`-Block bauen:
   ```json
   {
     "status": "<gruen|gelb|rot>",
     "tiefenstufe": <int 1-5>,
     "konfidenz": "<hoch|mittel|niedrig>",
     "ist_kernsanierung": <bool>,
     "massnahmen_liste": [
       {
         "kategorie": "<Dach|Fassade|Fenster|Heizung|Elektrik|Sanitaer|Boeden|Grundriss|Sonstiges>",
         "ist_zustand": "<string>",
         "geplant": "<string>",
         "kosten_netto_eur": <number>
       }
     ],
     "rnd_gutachten_netto_eur": <number = 600 × N_WE>,
     "weg_teilung_netto_eur": <number>,
     "enev_klasse": "<A+..H|unbekannt>",
     "summen": {
       "modernisierung_netto_eur": <number>,
       "modernisierung_brutto_eur": <number>,
       "nebenkosten_netto_eur": <number>,
       "nebenkosten_brutto_eur": <number>
     }
   }
   ```
2. **Asset-Trennung-Pflichtcheck** vor State-Write: kein `massnahmen_liste`-Eintrag enthält `subvention`/`rücklage`/`ruecklage` (Validator-Doppelcheck).
3. `objekt.letzter_modul_lauf` auf `"modul_4"` setzen.
4. **Modul 2 nicht anfassen** — `modul_3.rnd_jahre` und `modul_3.rnd_frozen` bleiben unverändert. (Schema-Constraint enforced ohnehin.)
5. State schreiben.
6. `runs/<slug>/modul-3-output.md` mit Zonen A/B/C schreiben.
7. Validator-Lauf: `python tools/validate_state.py runs/<slug>/state.json`. Exit 0 = OK; ≠0 → state.json zurückrollen, Fehlertext.

## 6. Self-Check (Pflicht vor Übergabe)

- [ ] `leerstand_we_anzahl` explizit gesetzt (nicht implizit alle WE)
- [ ] WE-Reno-Kosten basiert auf `leerstand_wohnflaeche_qm`, nicht auf Gesamtfläche
- [ ] Alle Pflichtfelder befüllt (status, tiefenstufe, konfidenz, ist_kernsanierung, leerstand_we_anzahl, leerstand_wohnflaeche_qm, massnahmen_liste, rnd_gutachten_netto_eur, weg_teilung_netto_eur, enev_klasse, summen)
- [ ] `massnahmen_liste` enthält RND-Gutachten-Eintrag und WEG-Teilung-Eintrag
- [ ] `rnd_gutachten_netto_eur == 600 × len(modul_2.we_liste)`
- [ ] **Asset-Trennung**: in keinem `massnahmen_liste`-Eintrag steht `subvention`/`rücklage`/`ruecklage` in `kategorie`/`ist_zustand`/`geplant`
- [ ] `modul_3.rnd_frozen` unverändert auf `true`
- [ ] Summen rechnerisch korrekt (Stichprobe: `modernisierung_netto_eur ≈ Σ kosten_netto_eur`)
- [ ] `modernisierung_brutto_eur ≈ modernisierung_netto_eur × 1.19` (±1 €)
- [ ] Excel-Transfer-Block (RENO-Sheet) ausgefüllt — siehe `docs/excel_handoff.md`
- [ ] `modul-3-output.md` erzeugt
- [ ] Validator-CLI exit 0

Bei rot → kein state.json-Schreiben, an Orchestrator zurück mit Fehlertext.

## 7. Chat-Visualisierung + Übergabe an Orchestrator (Pflicht-Reihenfolge)

**Schritt 1 — Pflicht-Visualisierung im Chat (NIE überspringen):** Den kompletten Zonen-Output 1:1 im Chat rendern — identisch zu dem, was in die Audit-Datei geschrieben wurde: Zone A (Massnahmen-Tabelle, Summen + Nebenkosten, Eckdaten als Markdown-Tabellen), Zone B, Zone C, Excel-Transfer-Vorschau. Grundsatz: **Alles, was später in PDF oder Excel landet, hat der User hier gesehen.** Ein Einzeiler ist NIE ausreichend — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

**Schritt 2 — Status-Zeile (NACH der Visualisierung):**
```
Modul 4 grün. <K> Massnahmen, Mod-Summe <Σ> € netto. Werte in runs/<slug>/state.json, Audit in runs/<slug>/modul-3-output.md.
```

Die Weiter-Frage stellt der Orchestrator als klickbares `AskUserQuestion`-Gate — das Modul stellt selbst KEINE Freigabe-Frage.

============================================================

## Änderungen

- **2026-06-11 — Gate-Härtung + Pflicht-Visualisierung** nach Datteln-Lauf (`plans/2026-06-11-orchestrator-gate-haertung-visualisierung.md`): Sektion 7 von „Eine Zeile" auf Pflicht-Reihenfolge Visualisierung (Zonen A/B/C 1:1 + Excel-Transfer-Vorschau) → Status-Zeile umgestellt; neue Sektion 1a Entscheidungs-Weichen (> ±5 % nie autonom — Massnahmen-Kosten, WEG-Kosten, WE-Reno-Stufe, Nebenkosten-Quote); neuer Pflicht-Block „Excel-Transfer-Vorschau" in Sektion 4; Status-Zeile auf echte Modul-Nummer (4) korrigiert. Audit-Dateiname `modul-3-output.md` bewusst unverändert (Bestands-Vertrag).
