---
name: aufteiler-modul-3-rnd-afa
description: Modul 3 der Aufteiler-Analyse — Restnutzungsdauer und AfA (ImmoWertV-basiert, mit rnd_frozen-Mechanik). Wird vom aufteiler-Orchestrator aufgerufen. Seit 2026-06-11 Pflicht-Visualisierung des kompletten Zonen-Outputs + Excel-Transfer-Vorschau im Chat vor dem Orchestrator-Gate; Entscheidungs-Weichen > ±5 % nie autonom auflösen. Seit 2026-10-15 (v2.0) Modernisierungspunkte nach der DIMBEG-Matrix (5-Jahres-Stufen je Gewerk, > 20 J. = 0, Teilerneuerung anteilig) statt 15/25-Jahres-Hausregel, Alter bis Übergang Nutzen/Lasten, Mindest-RND 12 J., Kohärenz-Check RND ↔ Gebäudeanteil; Wissensfragen zu RND/AfA ohne Objekt aus references/dimbeg-rnd-afa-wissen.md.
---

# Modul 3 — Restnutzungsdauer und AfA

Regelbasierte Vorprüfung der RND und des AfA-Korridors nach ImmoWertV 2021 Anlage 2. Alles deterministisch im Modul (Sektion 3): Punkte nach DIMBEG-Matrix, RND nach amtlicher Formel + Tabelle 3 der ImmoWertV 2021 Anlage 2. Kein Notion-Lookup mehr (das Notion-Regelwerk R03/R04 + a/b/c ist veraltet). Setzt `rnd_frozen=true` nach Lauf — Module 4–6 dürfen `rnd_jahre` nicht überschreiben.

**Wissensbasis:** `references/dimbeg-rnd-afa-wissen.md` (DIMBEG-Matrix, Ausschlüsse, Kohärenz RND ↔ Kaufpreisaufteilung, 15-%-Regel, Finanzamt, Risiken, FAQ). Vor jedem Lauf und vor jeder Antwort auf eine RND/AfA-Frage lesen.

Ersetzt KEIN Gutachten und keine sachverständige Einzelfall-Würdigung (BFH IX R 7/23). Steuerberater einbinden vor Kauf-Entscheidung.

## 1. State laden (Pflicht — erste Aktion)

1. Vom Orchestrator bekomme ich `objekt_slug`. Pfad: `runs/<objekt_slug>/state.json`.
2. State einlesen mit `Read`.
3. Pflicht-Vorgänger-Felder prüfen. Wenn etwas fehlt → STOPP, Antwort an Orchestrator:
   `"Modul 2: Pflichtfeld <pfad> fehlt. Bitte Modul 1 erneut laufen lassen."`

**Pflicht-Vorgänger:** `modul_2.we_liste` (mindestens 1 WE).

**Re-Run-Sperre:** Wenn `modul_3.rnd_frozen === true` bereits gesetzt → STOPP: `"Modul 3 wurde bereits gelaufen, RND ist gefroren. Re-Run nur via Orchestrator nach explizitem Reset des modul_3-Blocks (manuell aus state.json entfernen)."`

## 1a. Entscheidungs-Weichen während des Modullaufs (Pflicht-Regel)

Trifft das Modul auf eine echte Weiche — eine Annahme-Entscheidung mit Effekt > ±5 % auf ein Modul-Ergebnis (RND, AfA-Empfehlung) — SOFORT `AskUserQuestion` stellen, mit der eigenen Empfehlung als erster Option (Suffix „(Empfehlung)"). Solche Weichen NIE autonom mit der eigenen Empfehlung auflösen — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

Typische Weichen in diesem Modul:
- Mehrdeutige Sanierungsjahr-Angaben (z.B. „vor ein paar Jahren") an den Stufengrenzen 5/10/15/20 Jahre der DIMBEG-Matrix — der Punkte-Sprung verschiebt den Mod-Score und damit die RND-Formel
- Unklarer Umfang einer Teilerneuerung (z.B. „ein paar Fenster getauscht") bei Dach/Fassade (je 4 Punkte)
- Kernsanierungs-Einstufung (alles bis auf die Grundmauern neu?) — entscheidet zwischen RND-Vorprüfung und Quasi-Neubau
- Baujahr unklar/widersprüchlich zwischen Quellen (Exposé vs. Energieausweis)
- Stichtag (Übergang Nutzen/Lasten) unbekannt und eine Maßnahme liegt so, dass das Stichtagsjahr die Stufe wechselt

**Keine Weiche:** R02 (fehlende Gewerk-Angabe = 0 Punkte) bleibt deterministische Hauptregel — NICHT durch Nachfragen ersetzen, nur in Zone C ausweisen.

Ohne Weichen läuft das Modul autonom durch — endet aber IMMER in der Pflicht-Visualisierung (Sektion 7) + dem Freigabe-Gate des Orchestrators.

## 2. Inputs erheben

Per `AskUserQuestion` einzeln:

1. **Baujahr des Gebäudes** — Format: einzelne Zahl, z.B. `1968`. Plausi: zwischen 1850 und aktuelles Jahr.
2. **Bewertungsstichtag = Übergang Nutzen und Lasten** — Jahr (z.B. `2027`). Unbekannt → geplantes Übergangsjahr aus Kaufvertragsentwurf/Exposé; gibt es keins: aktuelles Jahr + Hinweis in Zone C. Alle Alter (Gebäude und Maßnahmen) werden bis zu diesem Jahr gerechnet: `stichtag_jahr`.
3. **Modernisierungsstand pro Gewerk** — User liefert pro Gewerk: Sanierungsjahr (oder `keine`/`unbekannt`) und den Umfang. Eine Zeile pro Gewerk, Format:
   `<Gewerk>: <Jahr> komplett` · `<Gewerk>: <Jahr> teilweise <Anteil %>` · `<Gewerk>: keine`.
   Gewerk-Liste (8 Stück, ImmoWertV Anlage 2 Tab 1 / DIMBEG-Matrix):
   - `Dach inkl. Daemmung` (max 4 Punkte)
   - `Fassade / Aussenwaende (Waermedaemmung)` (max 4 Punkte)
   - `Fenster / Aussentueren` (max 2 Punkte)
   - `Leitungssysteme (Strom, Gas, Wasser, Abwasser)` (max 2 Punkte)
   - `Heizungsanlage` (max 2 Punkte)
   - `Baeder` (max 2 Punkte)
   - `Innenausbau (Decken, Boeden, Treppen)` (max 2 Punkte)
   - `Grundrissverbesserung` (max 2 Punkte, ohne Umfang-Angabe)
   User darf alle 8 Zeilen auf einmal liefern. **R02 (Hauptregel):** Fehlende Angabe = 0 Punkte = Baujahr-Stand. NIE positiv schätzen.
   **R08 (Umfang ist Pflicht, nie pauschal Max-Punkte):** „Fassade gemacht", „neue Fenster", „Dach saniert" reicht NICHT für volle Punkte. Für jedes Gewerk mit Jahr den Umfang konkret erheben, als Bruch aus Zählbarem (Tabelle unten). `komplett` nur, wenn belegt ist, dass das ganze Bauteil erneuert wurde (Rechnung, Modernisierungsliste, Energieausweis, Exposé-Wortlaut „komplett", Besichtigung). Umfang unklar → nachfragen (Weiche, Sektion 1a). Bleibt er unklar: den niedrigsten plausiblen Anteil ansetzen und in Zone C als Risiko benennen — nie 100 %.

   | Gewerk | Umfang = | Beispiel |
   |---|---|---|
   | Fassade / Außenwände | gedämmte Wandfläche / gesamte Außenwandfläche; ohne m²: gedämmte Seiten / alle Außenseiten | nur Straßen- und Rückseite von 4 Seiten = 0,5; eine Giebelwand = 0,25 |
   | Dach inkl. Dämmung | erneuerte + gedämmte Dachfläche / gesamte Dachfläche; nur Eindeckung ohne Dämmung oder nur oberste Geschossdecke = höchstens 0,5 | eine Dachseite von zwei = 0,5 |
   | Fenster / Außentüren | getauschte Fenster + Türen / alle | 8 von 20 = 0,4 |
   | Leitungssysteme | sanierte Stränge bzw. Medien (Strom, Gas, Wasser, Abwasser) / alle | nur Elektrik = 0,25 |
   | Heizungsanlage | nur Wärmeerzeuger (Kessel/Therme) getauscht = 0,5; Erzeuger + Verteilung/Heizkörper = 1,0; Etagenthermen: getauschte / alle WE | 3 von 6 Thermen = 0,5 |
   | Bäder | sanierte Bäder / alle Bäder (je WE) | 2 von 8 WE = 0,25 |
   | Innenausbau | erneuerte WE bzw. Fläche (Decken, Böden, Treppen) / alle | Treppenhaus + 2 von 8 WE ≈ 0,3 |
   **R06 (Ausschluss):** Rein optische Maßnahmen (Streichen, Tapeten, neue Küche, Bodenbelag ohne Unterbau) zählen nicht und werden als `keine` gewertet — in Zone A Begründung `R06 optisch`.
4. **Kernsanierung?** — Nur fragen, wenn Angaben darauf hindeuten (fast alle Gewerke < 5 J. komplett, oder User nennt „kernsaniert"). Ja → **R07:** Quasi-Neubau, RND-Vorprüfung entfällt (Sektion 3b Schritt 0).
5. **Aufteiler-Massnahmen (geplant)** — falls bereits aus Sparring-Phase bekannt, sonst leer lassen (kommt erst in Modul 4 final). Format wie Modernisierungsstand, Jahr = geplantes Fertigstellungsjahr. Bei gleichzeitiger Bestand-Sanierung gewinnt das jüngere Jahr.

Matrix, Stufengrenzen und Ausschlüsse: `references/dimbeg-rnd-afa-wissen.md` Sektion 1–2.

## 3. Berechnung / Logik

**3a) Tiefenstufen-Wahl:**

| Stufe | Eingang vorhanden | Output |
|-------|-------------------|--------|
| 1 | Baujahr | Standard-RND nach ImmoWertV Anlage 2 (Basis-Formel) |
| 2 | + Modernisierungsstand pro Gewerk | Mod-Score, Mod-Formel angewendet, AfA-Korridor |
| 3 | + geplante Aufteiler-Massnahmen + Stichtag aus Vertrag + Umfang je Gewerk belegt | Post-Sanierungs-AfA, differenzierte Punkte |

**`tiefenstufe` ist im Schema 1–3.** Default-Ziel: Stufe 2.

**3b) Berechnung in fester Reihenfolge — RND-Formel deterministisch im Modul:**

Konstanten (NICHT aus Notion, fest im Modul):

```
GND = 80                         # MFH, ImmoWertV Anlage 1
MIN_RND = 12                     # Mindest-RND Wohnimmobilien (DIMBEG-Praxiswert, deckt sich mit dem Tiefpunkt der amtlichen Kurve bei 0 Punkten ≈ 11,75 J.)
MAX_QUOTE = 0.70                 # RND höchstens 70 % GND (ImmoWertV Anlage 2 II.2)
```

DIMBEG-Modernisierungsmatrix (fest im Modul, NICHT aus Notion — Notion-Regeln R03/R04 sind seit v2.0 abgelöst). Spalte = Altersstufe der Maßnahme, Wert = Punkte bei kompletter Erneuerung:

| Gewerk | Max | S1 < 5 J. | S2 5 bis < 10 | S3 10 bis < 15 | S4 15 bis 20 | > 20 J. |
|---|---|---|---|---|---|---|
| Dach inkl. Daemmung | 4 | 4,0 | 3,0 | 2,0 | 1,0 | 0 |
| Fassade / Aussenwaende | 4 | 4,0 | 3,0 | 2,0 | 1,0 | 0 |
| Fenster / Aussentueren | 2 | 2,0 | 2,0 | 1,0 | 0 | 0 |
| Heizungsanlage | 2 | 2,0 | 2,0 | 1,0 | 0 | 0 |
| Leitungssysteme | 2 | 2,0 | 2,0 | 2,0 | 1,0 | 0 |
| Baeder | 2 | 2,0 | 1,0 | 0 | 0 | 0 |
| Innenausbau | 2 | 2,0 | 2,0 | 2,0 | 1,0 | 0 |
| Grundrissverbesserung | 2 | 2,0 | 1,5 | 1,0 | 0,5 | 0 |

Variablen a/b/c und relatives Mindestalter — **amtlich, ImmoWertV 2021 Anlage 2 Tabelle 3** (wörtlich übernommen von gesetze-im-internet.de am 2026-10-15; fest im Modul, kein Notion-Lookup mehr):

| Punkte | a | b | c | ab relativem Alter | Modernisierungsgrad (Tab. 2) |
|---|---|---|---|---|---|
| 0 | 1,2500 | 2,6250 | 1,5250 | 60 % | nicht modernisiert (0–1) |
| 1 | 1,2500 | 2,6250 | 1,5250 | 60 % | |
| 2 | 1,0767 | 2,2757 | 1,3878 | 55 % | kleine Modernisierungen (2–5) |
| 3 | 0,9033 | 1,9263 | 1,2505 | 55 % | |
| 4 | 0,7300 | 1,5770 | 1,1133 | 40 % | |
| 5 | 0,6725 | 1,4578 | 1,0850 | 35 % | |
| 6 | 0,6150 | 1,3385 | 1,0567 | 30 % | mittlerer Grad (6–10) |
| 7 | 0,5575 | 1,2193 | 1,0283 | 25 % | |
| 8 | 0,5000 | 1,1000 | 1,0000 | 20 % | |
| 9 | 0,4660 | 1,0270 | 0,9906 | 19 % | |
| 10 | 0,4320 | 0,9540 | 0,9811 | 18 % | |
| 11 | 0,3980 | 0,8810 | 0,9717 | 17 % | überwiegend modernisiert (11–17) |
| 12 | 0,3640 | 0,8080 | 0,9622 | 16 % | |
| 13 | 0,3300 | 0,7350 | 0,9528 | 15 % | |
| 14 | 0,3040 | 0,6760 | 0,9506 | 14 % | |
| 15 | 0,2780 | 0,6170 | 0,9485 | 13 % | |
| 16 | 0,2520 | 0,5580 | 0,9463 | 12 % | |
| 17 | 0,2260 | 0,4990 | 0,9442 | 11 % | |
| 18 | 0,2000 | 0,4400 | 0,9420 | 10 % | umfassend modernisiert (18–20) |
| 19 | 0,2000 | 0,4400 | 0,9420 | 10 % | |
| 20 | 0,2000 | 0,4400 | 0,9420 | 10 % | |

(Bis v1.x stand hier eine gruppierte Tabelle mit falschen Werten und eine selbst erfundene F(x)-Formel. Ergebnis war u. a. nicht monoton: mehr Punkte ergaben teils eine kürzere RND. Seit v2.0 ersetzt durch das amtliche Modell.)

**Schritt 0 — R07 Kernsanierung:**

Ist das Gebäude kernsaniert (alles bis auf die Grundmauern neu): KEINE RND-Formel. Quasi-Neubau, RND startet neu, RND-Gutachten sinnlos. `rnd_jahre = 50` (gesetzliche Standard-AfA 2 %, DIMBEG: „bis zu 50 Jahre AfA"), `status = "gelb"`, `rnd_basis = "R07 Kernsanierung — Quasi-Neubau, AfA nach Neubau-Regeln mit Steuerberater klären"`. Weiter mit Schritt 7. (ImmoWertV Anlage 2 II.1: bei Kernsanierung Baujahr = Sanierungsjahr, RND bis 90 % GND — für den Verkehrswert, nicht für den AfA-Hebel.)

**Schritt 1 — Mod-Score (Punkte) nach DIMBEG-Matrix:**

Pro Gewerk:
```
jahr = jüngeres aus (bestand_jahr, aufteiler_jahr)      # fehlt beides → R02
if jahr fehlt oder Massnahme rein optisch:
    punkte_gewerk = 0                                    # R02 / R06
else:
    alter_massnahme = stichtag_jahr − jahr
    stufe = S1 if alter_massnahme < 5
          else S2 if alter_massnahme < 10
          else S3 if alter_massnahme < 15
          else S4 if alter_massnahme <= 20
          else 0                                         # > 20 J. = 0 Punkte
    matrixwert = DIMBEG_MATRIX[gewerk][stufe]
    if gewerk == Grundrissverbesserung:
        punkte_gewerk = matrixwert                       # feste 100/75/50/25-%-Stufen, kein Umfang
    else:
        punkte_gewerk = matrixwert × umfang_anteil       # komplett = 1.0, teilweise = Anteil (0.1…1.0)
```

```
mod_score = round(Σ punkte_gewerk, 1)  # 0..20
```

**Schritt 2 — Variablen-Lookup:**

```
punkte_tab = round_half_up(mod_score)        # ganze Punktzahl für Tabelle 3 (z. B. 4,5 → 5)
(a, b, c, rel_alter_schwelle) = TABELLE_3[punkte_tab]
```

**Schritt 3 — Basis-Werte:**

```
alter = stichtag_jahr − baujahr
alter_modell = min(alter, GND)               # Modell gilt bis Alter = GND; darüber stiege die Parabel wieder an (Bj 1905 ergäbe sonst 33 J.)
rel_alter = alter_modell / GND × 100         # ImmoWertV: relatives Alter in %
```

**Schritt 4 — R05 (Modell erst ab relativem Mindestalter):**

```
if rel_alter < rel_alter_schwelle:
    rnd_roh = GND − alter_modell             # ImmoWertV: unterhalb der Schwelle RND = GND − Alter
    rnd_basis = "RND = GND − Alter (relatives Alter {rel_alter:.0f} % < {rel_alter_schwelle} %)"
else:
    # Schritt 5
```

**Schritt 5 — Modernisierungs-Formel (ImmoWertV Anlage 2 II.2, amtlich):**

```
rnd_roh = a × alter_modell² / GND − b × alter_modell + c × GND
rnd_basis = "ImmoWertV-Formel (Mod-Score {mod_score} → Tabelle {punkte_tab} Punkte, a={a}, b={b}, c={c})"
```

**Schritt 6 — Grenzen:**

```
rnd_jahre = round(max(MIN_RND, min(rnd_roh, GND × MAX_QUOTE)))
```

Gegenprobe (im Output dokumentieren): 0 Punkte, Alter 60, GND 80 → Formel 20,75 J. ≈ GND − Alter 20 J. (Kurve schließt an die Basis an). 0 Punkte, Alter ≥ 80 → 12 J. (= MIN_RND). Durchgerechnet für Alter 0–130 und alle Punktzahlen: nach Rundung wird die RND mit mehr Punkten nie kürzer.

Referenzfälle (Stichtag 2026, zum Nachrechnen):

| Fall | Punkte | RND | AfA-Empfehlung |
|---|---|---|---|
| Bj 1962, Dach 2004, Fenster 2012, Heizung 2016, Bad 2018 (alles komplett) | 3 | 23 J. | 4,15 % |
| Bj 1905, nichts modernisiert | 0 | 12 J. | 7,95 % |
| Bj 1970, Dach 2022, Fassade 2022 (50 %), Fenster 2020, Heizung 2023, Leitungen 2015, Bad + Innenausbau 2019 | 15 | 52 J. | 1,84 % |

**Schritt 7 — AfA-Korridor + Empfehlung:**

```
afa_oben = 100 / rnd_jahre              # kürzere RND = höherer AfA
afa_unten = 100 / (rnd_jahre × 1.10)    # Sachverständigen-Spielraum +10 %
afa_empfehlung = (afa_oben + afa_unten) / 2

afa_korridor_prozent = { "min": round(afa_unten, 2), "max": round(afa_oben, 2) }
afa_empfehlung_prozent = round(afa_empfehlung, 2)
```

**Schritt 8 — Status-Ableitung:**

- `afa_empfehlung_prozent >= 3.0` → `status = "gruen"` (starker Hebel, Gutachten lohnt)
- `2.0 <= afa_empfehlung_prozent < 3.0` → `status = "gelb"` (Standard, Gutachten prüfen)
- `afa_empfehlung_prozent < 2.0` → `status = "gelb"` (Standard 2 % reicht, kein Hebel)
- Wenn `rnd_jahre < 12` oder `rnd_jahre > 80` → `status = "rot"` (außerhalb Plausi-Grenzen, Schema lehnt ab)

**3c) Plausibilitäts-Prüfung:**

- `baujahr` zwischen 1850 und 2030 (Schema).
- `rnd_jahre` zwischen 12 und 80 (Schema-Grenze). Wenn raus → Status rot, kein Schreiben.
- `afa_empfehlung_prozent` zwischen 0 und 10 (Schema).
- `mod_score` zwischen 0 und 100 (Schema; effektiv 0–20).
- Selbstvalidierungs-Test (im Modul-Output dokumentieren): Bei relativem Alter unter der Schwelle MUSS `rnd_jahre == max(MIN_RND, GND − alter)` sein. Monotonie: Mit einem Punkt mehr darf die RND bei gleichem Alter nie kürzer werden. Bei Abweichung → Bug, Status rot.

**3d) Kohärenz-Check RND ↔ Kaufpreisaufteilung (Pflicht, wenn `modul_2.gebaeude_anteil_prozent` vorhanden):**

RND und Gebäudeanteil müssen zusammenpassen — sonst kippt das Finanzamt eher die Aufteilung (Wissensbasis Sektion 4). Beide Werte in Zone A Block 2 nebeneinander zeigen:

```
rnd_quote = rnd_jahre / GND      # Anteil der Gesamtnutzungsdauer, der noch übrig ist
```

Kurze RND heißt: Gebäude weitgehend verbraucht. Steht daneben ein hoher Gebäudeanteil, ist das ein Widerspruch. Keine harte Schwelle — in Zone C unter Risiken in einem Satz einordnen (passt / Widerspruchsrisiko + Begründung). Fehlt `modul_2.gebaeude_anteil_prozent`: Zeile „Gebäudeanteil: noch offen (Modul 2)" und Hinweis, vor dem Kauf beide Ersteinschätzungen einzuholen.

## 4. Output erzeugen (Drei Zonen)

**Zone A — Daten-Block (pixel-identisch über alle Objekte):**

Block 1 — Gewerk-Punkte:
```
| Gewerk                            | Max | Jahr (Bestand/Aufteiler) | Alter | Stufe | Umfang | Punkte | Begründung |
|-----------------------------------|-----|--------------------------|-------|-------|--------|--------|------------|
| Dach inkl. Daemmung               | 4   | <Jahr/—> (B/A)           | <J>   | S1–S4/>20 | <%>  | <P>    | DIMBEG/R02/R06 |
| Fassade / Aussenwaende            | 4   | …                        | …     | …     | …      | …      | … |
| Fenster / Aussentueren            | 2   | …                        | …     | …     | …      | …      | … |
| Leitungssysteme                   | 2   | …                        | …     | …     | …      | …      | … |
| Heizungsanlage                    | 2   | …                        | …     | …     | …      | …      | … |
| Baeder                            | 2   | …                        | …     | …     | …      | …      | … |
| Innenausbau                       | 2   | …                        | …     | …     | …      | …      | … |
| Grundrissverbesserung             | 2   | …                        | …     | …     | —      | …      | … |
| Gesamt                            | 20  |                          |       |       |        | <M>    |   |
```

Block 2 — AfA-Korridor:
```
| Parameter                            | Wert                                  |
|--------------------------------------|---------------------------------------|
| GND Gebäude (MFH)                    | 80 Jahre                              |
| Baujahr                              | <Jahr>                                |
| Stichtag (Übergang Nutzen/Lasten)    | <Jahr> (<Quelle: Vertrag/geplant/angenommen>) |
| Alter zum Stichtag                   | <Alter> Jahre                         |
| Modernisierungspunkte (mod_score)    | <M> von 20                            |
| Modernisierungsgrad                  | <Bezeichnung>                         |
| Punkte für Tabelle 3 (gerundet)      | <P>                                   |
| Variablen (a, b, c, Schwelle)        | a=<a>, b=<b>, c=<c>, ab rel. Alter <S> % |
| Relatives Alter (Alter / GND)        | <rel> %                               |
| Rechenweg                            | ImmoWertV-Formel / RND = GND − Alter  |
| RND roh (vor Grenzen 12 J. / 70 %)   | <roh> Jahre                           |
| RND_jahre (final, gefroren)          | <RND> Jahre                           |
| AfA-Korridor                         | <unten> % bis <oben> %                |
| AfA-Empfehlung (Mitte)               | <empf> %                              |
| RND-Quote (RND / GND)                | <q> %                                 |
| Gebäudeanteil (Modul 2)              | <g> % / noch offen                    |
| Kohärenz RND ↔ Gebäudeanteil         | passt / Widerspruchsrisiko            |
```

**Zone B — Tiefenstufen-Deklaration (genau zwei Zeilen):**

```
Tiefenstufe: <N> von 3 (<Begründung wenn nicht 3>)
Konfidenz: <hoch|mittel|niedrig>
```

**Zone C — Begründungs-Block:**

1. **Wichtigste Annahmen** (max 5 Bullets) — z.B. „GND 80 J für MFH (ImmoWertV Anlage 1)", „Punkte nach DIMBEG-Matrix, Stichtag 2027 (geplanter Übergang)", „Variablen-Tabelle aus ImmoWertV Anlage 2 Tab 3 (Default, Notion-Lookup nicht durchgeführt)".
2. **Risiken / Unsicherheiten** (max 5 Bullets) — Pflicht-Bullets:
   - Kohärenz RND ↔ Gebäudeanteil (Sektion 3d) in einem Satz.
   - „Bundesrats-Vorschlag zur Abschaffung von RND-Gutachten für Bestandsgebäude — noch kein Gesetz (Stand 2026-10-15)."
   Dazu objektbezogen, z.B. „Heizung-Sanierungsjahr unbekannt → 0 Punkte (R02)", „Aufteiler-Massnahmen noch nicht final aus Modul 4, Punkte können steigen".
3. **Empfehlung** (1–3 Sätze) — z.B. „AfA 3,1 % rechtfertigt Gutachten (~2.000 €) für Käufer. Standard 2 % reicht nicht. Gutachten mit Besichtigung und parallel Kaufpreisaufteilung beauftragen, Steuerberater vor Kauf einbinden."

**BFH-Pflichthinweis (immer in Zone C am Ende anhängen, byte-identisch):**

```
WICHTIG: Diese Berechnung ist eine regelbasierte Vorprüfung nach ImmoWertV 2021 Anlage 2.
Sie ersetzt KEIN Gutachten eines öffentlich bestellten Sachverständigen
(BFH IX R 7/23). Steuerberater vor Kauf einbinden.
```

**Excel-Transfer-Vorschau (Pflicht-Block nach Zone C):**

Tabelle der Zellen, die die Werte DIESES Moduls später (physischer Write erst in Modul 6 nach separater Freigabe) befüllen — Zell-Verträge aus `docs/excel_handoff.md`:

```
| Sheet!Zelle               | Wert                                            |
|---------------------------|-------------------------------------------------|
| BESICHTIGUNG!B8           | <Baujahr>                                       |
| KALKU!H10 (Comment)       | AfA <empf> % (Korridor <min>–<max> %), RND <X> J, Mod-Score <M>/20 |
| KALKU!E36 (optional)      | <Baujahr Heizung, falls aus Gewerk-Angaben bekannt> |
```

(RND/AfA haben kein dediziertes KALKU-Feld — sie landen als Excel-Comment auf `KALKU!H10` + PDF Sektion 6.)

## 5. State persistieren

1. `modul_3`-Block bauen:
   ```json
   {
     "status": "<gruen|gelb|rot>",
     "tiefenstufe": <int 1-3>,
     "konfidenz": "<hoch|mittel|niedrig>",
     "baujahr": <int>,
     "rnd_jahre": <int 12-80>,
     "rnd_frozen": true,
     "rnd_basis": "<Rechenweg: ImmoWertV-Formel mit Punkten/a/b/c oder GND − Alter, Stichtag>",
     "mod_score": <number 0-100>,
     "afa_korridor_prozent": { "min": <number>, "max": <number> },
     "afa_empfehlung_prozent": <number>,
     "begruendung": "<Kurzfassung Zone C Annahmen+Empfehlung>"
   }
   ```
2. **`rnd_frozen` MUSS auf `true` gesetzt sein** (Schema-Constraint, sonst Validator-Fail).
3. `objekt.letzter_modul_lauf` auf `"modul_3"` setzen.
4. State schreiben.
5. `runs/<slug>/modul-2-output.md` mit Zonen A/B/C schreiben.
6. Validator-Lauf: `python tools/validate_state.py runs/<slug>/state.json`. Exit 0 = OK; ≠0 → state.json zurückrollen, Fehlertext.

## 6. Self-Check (Pflicht vor Übergabe)

- [ ] Alle Pflichtfelder befüllt (status, tiefenstufe, konfidenz, baujahr, rnd_jahre, rnd_frozen, rnd_basis, mod_score, afa_korridor_prozent, afa_empfehlung_prozent, begruendung)
- [ ] `rnd_frozen === true`
- [ ] `rnd_jahre` zwischen 12 und 80
- [ ] `afa_empfehlung_prozent` zwischen 0 und 10
- [ ] `afa_korridor_prozent.min <= afa_korridor_prozent.max`
- [ ] Selbstvalidierung: unter der Schwelle ist `rnd_jahre == max(12, 80 − alter_modell)`; RND wächst mit den Punkten (Monotonie); Referenzfälle aus Schritt 6 reproduzierbar
- [ ] Punkte jedes Gewerks gegen DIMBEG-Matrix × Umfang nachgerechnet, Alter bis Stichtag (nicht bis heute)
- [ ] Kohärenz-Zeile RND ↔ Gebäudeanteil und Bundesrats-Risiko in Zone C
- [ ] BFH-Pflichthinweis in `modul-2-output.md` enthalten
- [ ] Excel-Transfer-Block (KALKU!C26..C28) ausgefüllt
- [ ] Validator-CLI exit 0

Bei rot → kein state.json-Schreiben, an Orchestrator zurück mit Fehlertext.

## 7. Chat-Visualisierung + Übergabe an Orchestrator (Pflicht-Reihenfolge)

**Schritt 1 — Pflicht-Visualisierung im Chat (NIE überspringen):** Den kompletten Zonen-Output 1:1 im Chat rendern — identisch zu dem, was in die Audit-Datei geschrieben wurde: Zone A (Gewerk-Punkte + AfA-Korridor als Markdown-Tabellen), Zone B, Zone C inkl. BFH-Pflichthinweis, Excel-Transfer-Vorschau. Grundsatz: **Alles, was später in PDF oder Excel landet, hat der User hier gesehen.** Ein Einzeiler ist NIE ausreichend — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

**Schritt 2 — Status-Zeile (NACH der Visualisierung):**
```
Modul 3 grün. RND <X> Jahre (gefroren), AfA-Empfehlung <Y> %. Werte in runs/<slug>/state.json, Audit in runs/<slug>/modul-2-output.md.
```

Die Weiter-Frage stellt der Orchestrator als klickbares `AskUserQuestion`-Gate — das Modul stellt selbst KEINE Freigabe-Frage.

## 8. Ersteinschätzung und Wissensfragen ohne State (Modus `afa_frage`)

Fragt André allgemein oder schnell nach RND/AfA („lohnt sich ein RND-Gutachten bei Baujahr 1962, Dach 2008?", „zählt eine neue Küche?", „was ist die 15-%-Regel?"), läuft KEIN Modul-Lauf mit State, Freeze und Validator:

1. `references/dimbeg-rnd-afa-wissen.md` lesen.
2. **Reine Wissensfrage:** aus Sektion 2–7 der Referenz antworten (FAQ-Tabelle als Muster), kurz, mit Quelle „DIMBEG, Stand 2026-10-15".
3. **Ersteinschätzung mit Objektdaten:** Rechnung aus Sektion 3b 1:1 anwenden (Matrix, Stichtag, MIN_RND, Formel, AfA-Korridor) und als kompakte Tabelle zeigen: Gewerk-Punkte, mod_score, RND, AfA-Korridor, Kohärenz-Hinweis. Fehlende Angaben nach R02 (0 Punkte) und offen benennen. Nichts in `runs/` schreiben.
4. Immer am Ende: BFH-Pflichthinweis (Sektion 4) + Bundesrats-Risiko in einem Satz.
5. Will André daraus eine echte Objekt-Analyse: an den Orchestrator verweisen (Modus `nur_rnd`, mit State und Freeze).

============================================================

## Änderungen

- **2026-10-15 — v2.0 DIMBEG-Modernisierungsmatrix** (`plans/2026-10-15-modul3-dimbeg-modernisierungsmatrix.md`, Quelle DIMBEG-Deep-Dive DERIC 2026-10-15): Punktevergabe von Hausregel R03/R04 (≤ 15 J. voll, 16–25 J. halb) auf DIMBEG-Matrix umgestellt (5-Jahres-Stufen je Gewerk, > 20 J. = 0, Teilerneuerung anteilig); Alter bis Übergang Nutzen/Lasten statt fix 2026; Mindest-RND 12 J. (statt 30-%-GND-Floor 24 J., gilt jetzt auch für die Basis-Formel — vorher lief ein unmodernisierter Altbau mit Alter > 80 auf RND 0 und damit Status rot); **Formel + a/b/c-Tabelle auf amtliches Modell ImmoWertV 2021 Anlage 2 korrigiert** (vorher selbst erfundene F(x)-Formel + gruppierte Tabelle mit falschen Werten, nicht monoton; Mod-Score ≥ 18 → 90-%-Cap entfernt, 90 % gilt laut Verordnung nur bei Kernsanierung); R06 optische Maßnahmen = 0; R07 Kernsanierung = Quasi-Neubau; R08 Umfang je Gewerk ist Pflicht, nie pauschal Max-Punkte (Zähl-Tabelle, unklar = niedrigster plausibler Anteil); Sektion 3d Kohärenz-Check RND ↔ Gebäudeanteil; Pflicht-Risiko Bundesrats-Vorschlag; neue Sektion 8 für Ersteinschätzung/Wissensfragen ohne State; Wissensbasis `references/dimbeg-rnd-afa-wissen.md`. Schema `modul_3.rnd_jahre` minimum 20 → 12. Titel-Tippfehler „Modul 2" → „Modul 3".

- **2026-06-11 — Gate-Härtung + Pflicht-Visualisierung** nach Datteln-Lauf (`plans/2026-06-11-orchestrator-gate-haertung-visualisierung.md`): Sektion 7 von „Eine Zeile" auf Pflicht-Reihenfolge Visualisierung (Zonen A/B/C 1:1 + Excel-Transfer-Vorschau) → Status-Zeile umgestellt; neue Sektion 1a Entscheidungs-Weichen (> ±5 % nie autonom, R02 bleibt deterministisch); neuer Pflicht-Block „Excel-Transfer-Vorschau" in Sektion 4; Status-Zeile auf echte Modul-Nummer (3) korrigiert. Audit-Dateiname `modul-2-output.md` bewusst unverändert (Bestands-Vertrag).
