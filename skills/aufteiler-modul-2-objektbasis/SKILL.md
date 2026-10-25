---
name: aufteiler-modul-2-objektbasis
description: Modul 2 der Aufteiler-Analyse — Objektbasis (BRW, Gebäudeanteil, WE-Liste). Wird ausschließlich vom aufteiler-Orchestrator aufgerufen. Seit 2026-06-11 (v1.4) Pflicht-Visualisierung des kompletten Zonen-Outputs + Excel-Transfer-Vorschau im Chat vor dem Orchestrator-Gate; Entscheidungs-Weichen > ±5 % nie autonom auflösen. Seit 2026-07-01 (v1.5) wird der Gebäudeanteil residual vom durchschnittlichen ETW-Verkaufspreis (`modul_1.eur_per_qm.median`) statt vom MFH-Einkaufspreis gerechnet (Aufteiler-Basis, höherer Gebäudeanteil); MFH-Residual nur noch als Plausi-Zeile in Zone C. Seit 2026-09-11 (v1.6) persistiert das Modul die Grundstücksfläche mit Quellen-Trail (Grundbuch-Bestandsverzeichnis vor Flurkarte vor Exposé; abgeschriebene Flurstücke zählen nicht) und Miteigentumsanteile je WE (Teilungserklärung; bei nicht geteilten Objekten Wohnflächenanteil als gekennzeichnete Schätzung) — beides speist den Bodenwert je WE im Reiter „Verkauf Cashflow". Ebenfalls seit v1.6: Garagen und Stellplätze als Verkaufs-Assets (Anzahl gesamt, Verkaufspreis je Einheit mit Quelle und Gate) für Kaufpreis, AfA (2 %/0 %), Cashflow und Verkaufsmatrix.
---

# Modul 1 — Objektbasis

Zentrale Erfassung der zwei Datenstrukturen, die alle anderen Module brauchen: WE-Liste (für Modul 2/3/4/5) und Boden/Gebäude-Aufteilung (für AfA-Bemessungsgrundlage in Modul 2/5). Keine Mietberechnung, keine Sanierungsplanung, keine AfA-Logik hier.

## 1. State laden (Pflicht — erste Aktion)

1. Vom Orchestrator bekomme ich `objekt_slug`. Pfad: `runs/<objekt_slug>/state.json`.
2. State einlesen mit `Read`.
3. Pflicht-Vorgänger-Felder prüfen. Wenn etwas fehlt → STOPP, Antwort an Orchestrator:
   `"Modul 1: Pflichtfeld <pfad> fehlt. Bitte Modul 0 erneut laufen lassen."`

**Pflicht-Vorgänger:** `modul_1.status` (Quick-Check muss gelaufen sein). Zusätzlich wird `modul_1.eur_per_qm.median` als ETW-Verkaufspreis-Basis für den Gebäudeanteil gelesen (siehe 3b) — bei `null` greift die Fallback-Kaskade / Weiche aus 1a.

## 1a. Entscheidungs-Weichen während des Modullaufs (Pflicht-Regel)

Trifft das Modul auf eine echte Weiche — eine Annahme-Entscheidung mit Effekt > ±5 % auf ein Modul-Ergebnis — SOFORT `AskUserQuestion` stellen, mit der eigenen Empfehlung als erster Option (Suffix „(Empfehlung)"). Solche Weichen NIE autonom mit der eigenen Empfehlung auflösen — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

Typische Weichen in diesem Modul:
- BORIS-Adress-/Kandidaten-Wahl (bereits Pflicht-Stop in 2a.3 — bleibt unverändert)
- Nutzungsart-Wahl bei > 20 % BRW-Differenz zwischen Ein/zweigeschossig und Misch-/Mehrgeschossig (2a.7), wenn sie den Gebäudeanteil > ±5 % verschiebt
- Geschätzte Wohnflächen, wenn der Schätzanteil Σ-Wohnfläche oder Gebäudeanteil > ±5 % bewegen kann (Optionen: Schätzwert als Empfehlung / User-Wert)
- **ETW-Preis-Quelle für den Gebäudeanteil (seit v1.5):** liefert Modul 1 keinen `eur_per_qm.median` (alle Portale null), wird der ETW-Verkaufspreis je m² als Weiche behandelt — `AskUserQuestion` nach dem ETW-€/m² (eigener Vorschlag als 1. Option, falls Einzel-Portalwerte vorliegen: deren Mittel). NIE still auf die MFH-Einkaufsbasis zurückfallen.

Ohne Weichen läuft das Modul autonom durch — endet aber IMMER in der Pflicht-Visualisierung (Sektion 7) + dem Freigabe-Gate des Orchestrators.

## 2. Inputs erheben

Per `AskUserQuestion` einzeln (eine Frage pro Aufruf):

1. **Adresse für BRW-Lookup** — falls nicht aus `objekt.adresse` ableitbar, präzisieren (PLZ + Straße + Hausnummer).
2. **Bodenrichtwert (BRW) in €/m²** — siehe **2a** (Auto-BRW-Lookup) für Pre-Fill via BORIS.NRW. Bei Lookup-Fehler manueller Eintrag aus https://www.boris.nrw.de/borisplus oder Notion-Preisdatenbank. Format: einzelne Zahl, z.B. `380`.
3. **Grundstücksfläche in m²** — Quellen-Rangfolge (seit v1.6 verbindlich): **Grundbuch-Bestandsverzeichnis** (Spalte „Größe" je Flurstück; abgeschriebene Flurstücke in Spalte 8 zählen NICHT mit) > Flurkarte/ALKIS > Exposé („ca."-Angabe, Konfidenz höchstens `mittel`). Pre-Fill aus `objektdaten.json` → `objekt.grundstueck_qm` anbieten, aber die Quelle nennen. Format: einzelne Zahl, z.B. `1341`. Ergebnis wird persistiert als `grundstuecksflaeche_qm` + `grundstuecksflaeche_quelle` (`quelle`, `dokument`, `flurstueck`, `konfidenz`, `abgerufen_am`) — die Fläche speist den Bodenwert je WE im Reiter „Verkauf Cashflow" und war bisher nur abgefragt, nie gespeichert.
4. **Anzahl Wohneinheiten (WE)** — Format: einzelne Zahl, z.B. `5`.
5. **WE-Liste** — pro WE eine Zeile, Format pro WE: `<WE-Nr>, <Lage>, <Wohnfläche m²>, <Zimmer>, <Balkon ja/nein>, <Keller ja/nein>`. Beispiel für eine Zeile:
   `1, EG, 92.98, 3, ja, ja`
   Lage-Schlüssel: `EG`, `OG_links`, `OG_rechts`, `DG_links`, `DG_rechts`, `Souterrain`, `Maisonette` (frei wählbar, lesbar).
   User darf mehrere Zeilen auf einmal liefern.
6. **Miteigentumsanteile (MEA) je WE** — seit v1.6. Quelle ist die **Teilungserklärung** (Zähler je Sondereigentum, gemeinsamer Nenner, z.B. `103/895`). Ist das Objekt **nicht geteilt** (`objektdaten.json` → `objekt.weg_bereits_geteilt = false`, keine TE im Datenraum), gibt es noch keine MEA: dann **Wohnflächenanteil als Schätzung** ansetzen — Zähler = `wohnflaeche_qm × 100` (ganzzahlig), Nenner = Σ aller Zähler — und `mea_quelle = "Wohnflaechenanteil_geschaetzt"` setzen. Nicht fragen, ob geschätzt werden darf: Teilungserklärungen bilden die MEA in der Praxis fast immer so; der Wert ist im Excel je WE überschreibbar, sobald die TE vorliegt. Persistiert als `we_liste[].mea_zaehler`, `mea_nenner`, `mea_quelle`. Der Validator lehnt Zähler > Nenner (einzeln und in Summe) ab.
7. **Garagen und Stellplätze als Verkaufs-Assets** (seit v1.6) — Anzahl gesamt (`garagen_gesamt`, `stellplaetze_gesamt`, aus Exposé/HV-Liste/Teilungserklärung) und **Verkaufspreis je Einheit** (`garage_preis_eur`, `stellplatz_preis_eur`): Marktansatz für den Aufteiler-Verkauf (Ruhrgebiet-Orientierung: Garage 8.000–15.000 €, Außenstellplatz 2.500–6.000 €; Exposé-Angabe oder Portal-Vergleich vor Schätzung). Quelle in `garagen_preis_quelle` (`Expose|Portal|User|geschaetzt`). Immer per `AskUserQuestion` bestätigen lassen (Preis-Weiche > ±5 % nie autonom). Die Zuordnung je Wohnung (Anzahl) erhebt Modul 5 aus der HV-Liste; Modul 6 schreibt je WE `Anzahl × Preis je Einheit` in den Reiter „Verkauf Cashflow" (Q/R) — dort fließen Garagen in Abgabepreis, Kaufpreis, AfA (Garage 2 %, Stellplatz 0 %), Cashflow und in die `VERKAUFSMATRIX` (Spalte V). Kein Objekt ohne Garagen: beide Anzahlen `0`, Preise leer.

**Falls Mieterliste/Wohnflächen unvollständig:** Schätzwerte erlaubt, in Zone C unter „Risiken" notieren. Lieber Schätzung als blockieren.

## 2a. Auto-BRW-Lookup (Pflicht vor Punkt 2)

**Ziel:** BRW automatisch aus BORIS.NRW über die offizielle OGC WMS GetFeatureInfo (`wms.nrw.de/boris/wms_nw_brw`) holen, dem User als Pre-Fill anbieten. Spart Tippfehler, liefert Audit-Trail (Bodenrichtwertnummer, Stichtag, bestätigte Adresse).

### 2a.1 Adresse zerlegen

Aus Punkt 1 (oben) extrahieren: `strasse`, `hausnr`, `plz`, `ort`. `objekt.adresse` ist üblicherweise eine Volltext-Form ("Deutsche Straße 59, 44339 Dortmund") — bei Bedarf splitten.

### 2a.2 Scraper aufrufen

Per `Bash`-Tool, cwd ist Repo-Root `Aufteiler/`:

```
python tools/m01_boris_brw.py --strasse "<strasse>" --hausnr "<hausnr>" --plz "<plz>" --ort "<ort>"
```

stdout enthält JSON, stderr enthält `[BRW]`-Logs. Exit-Code unterscheidet die Fälle:

| Exit | Bedeutung | JSON-Form |
|------|-----------|-----------|
| 0 | Eindeutiger Treffer, BRW geliefert | `{brw_eur_pro_qm, nutzungsart, bodenrichtwertnummer, gemeinde, gemarkung, ortsteil, plz, stichtag, bestaetigte_adresse, alle_nutzungsarten[], …}` |
| 1 | Lookup fehlgeschlagen (außerhalb NRW, keine Zone, Endpoint-Down) | `{error, adresse, grund?}` |
| 2 | Adresse mehrdeutig (Straßen-Mismatch, Hausnr nicht eindeutig, Fuzzy-Score) | `{error, grund, kandidaten: [{text, typ, score, plz, ort, ortsteil, bundesland}], adresse}` |

### 2a.3 exit 0 — Adress-Bestätigung (Pflicht-Stop VOR BRW-Anzeige)

Bei exit 0 liefert der Scraper im JSON `bestaetigte_adresse`, `gemarkung`, `ortsteil`, `geocoding_score`. **Bevor** der BRW-Wert angezeigt wird, muss der User die gefundene Adresse bestätigen — analog zu seinem manuellen BORIS-UI-Workflow (Adresse tippen, mit Pfeiltasten Kandidaten durchgehen, Enter, dann mit den Augen prüfen ob das richtig ist).

`AskUserQuestion`:

> BORIS hat verstanden:
> **<bestaetigte_adresse>**
> (Gemarkung <gemarkung oder "—">, Ortsteil <ortsteil>, Geocoding-Score <score>)
>
> Ist das die richtige Adresse?

Optionen:

- **Ja, Adresse stimmt** (default) → weiter zu 2a.4 (BRW-Pre-Fill).
- **Andere Adresse aus den Kandidaten** → siehe 2a.3a (Sub-Pfad).
- **Adresse manuell korrigieren** → User tippt neu (Adress-Felder aus Punkt 1 anpassen), Sektion 2a komplett neu durchlaufen ab 2a.2.

**Auch bei single-hit + Score≥2.5: Pflicht-Stop, kein Auto-Pick.** Default-Option ist Ja, ein Enter reicht — aber der User muss bewusst bestätigen. Die Scraper-Validierungs-Kaskade (Score/Straßen-Match/PLZ) ist ein Sicherheitsnetz, kein Ersatz für User-Confirm. Sie fängt bekannte Edge-Cases ab (Prosperstr.→Erdwegstr.-Bug 2026-05-19), garantiert aber nicht alle.

### 2a.3a Sub-Pfad „Andere Adresse" (Kandidaten-Auswahl)

Wenn der User in 2a.3 „Andere Adresse aus den Kandidaten" wählt:

1. Skill ruft Scraper erneut auf, diesmal mit `--mode geocode-only`:

   ```
   python tools/m01_boris_brw.py --strasse "<strasse>" --hausnr "<hausnr>" --plz "<plz>" --ort "<ort>" --mode geocode-only
   ```

2. Scraper liefert `kandidaten: [{text, typ, score, strasse, hausnr, plz, ort, ortsteil, bundesland, x, y}]` mit features[0..4] (alle, ohne Validierungs-Filter — der User pickt selbst).

3. `AskUserQuestion` mit den Kandidaten-Texten:

   > Welche Adresse meinst du?

   Optionen:
   - „<kandidaten[0].text> (Score <kandidaten[0].score>)"
   - „<kandidaten[1].text> (Score <kandidaten[1].score>)"
   - „<kandidaten[2].text> (Score <kandidaten[2].score>)"
   - „<kandidaten[3].text> (Score <kandidaten[3].score>)"
   - Option „Keine — Adresse manuell korrigieren" → User tippt neu, ab 2a.2.

4. Nach User-Wahl: Skill ruft Scraper im `--mode full` (default) erneut auf, **mit den Adress-Komponenten aus dem gewählten Kandidaten** (`strasse`, `hausnr`, `plz`, `ort`). Damit läuft die volle Pipeline (Validierungs-Kaskade + BRW-Lookup) gegen die vom User bestätigte Adresse.

5. Bei exit 0 zurück zu 2a.3 (Adress-Bestätigung) — diesmal mit der neuen Adresse, Default „Ja" reicht in der Regel.

### 2a.4 exit 0 — BRW-Pre-Fill anbieten (nach Adress-Bestätigung)

**Voraussetzung:** User hat in 2a.3 „Ja, Adresse stimmt" gewählt.

In Punkt 2 (BRW-Eingabe) statt blanker Frage:

> Bodenrichtwert (BRW) in €/m² — BORIS schlägt **<brw_eur_pro_qm>** €/m² vor (Nutzungsart **<nutzungsart>**, Bodenrichtwertnummer **<bodenrichtwertnummer>**, Gemarkung/Ortsteil <gemarkung oder ortsteil>, Stichtag <stichtag>).
> Übernehmen oder anderer Wert?

(Bestätigte Adresse ist hier nicht mehr nötig — wurde in 2a.3 bereits verifiziert.)

Bei **Übernahme**: `modul_2.brw_quelle.quelle = "BORIS.NRW_auto"` + alle Metadaten aus JSON.
Bei **Override** (User tippt eigene Zahl): `modul_2.brw_quelle.quelle = "BORIS.NRW_manuell"` mit dem User-Wert, aber Metadaten aus JSON erhalten (Bodenrichtwertnummer etc. bleiben Audit-Trail).

### 2a.5 exit 2 — Adress-Klärung per AskUserQuestion

User sieht `error` + `grund` + Kandidatenliste (formatiert lesbar). `AskUserQuestion` mit Optionen:

- Pro Kandidat (max 4): „<text>" → Adresse anpassen (z.B. PLZ aus Kandidat übernehmen) und 2a.2 erneut aufrufen.
- Option „Adresse selbst korrigieren" → User tippt korrigierte Komponenten ein, dann 2a.2 erneut.
- Option „BRW manuell eintragen" → auf Punkt 2 ohne Pre-Fill zurückfallen, `brw_quelle.quelle = "User_geschaetzt"` oder `"Notion"` je nach User-Quelle.

Beispiel-Phrasing für die Klärungs-Frage:
> BORIS hat die Adresse nicht eindeutig gefunden ("<grund>"). Vorschläge: <Kandidaten>. Welche Adresse meinst du?

### 2a.6 exit 1 — Manueller Fallback

User informieren in einer Zeile:
> BORIS-Lookup fehlgeschlagen: **<error>** (<grund falls vorhanden>). Bitte BRW manuell von https://www.boris.nrw.de/borisplus oder Notion-Preisdatenbank eintragen.

Dann Punkt 2 wie bisher (ohne Pre-Fill). `brw_quelle.quelle = "BORIS.NRW_manuell"` (User hat manuell auf BORIS geschaut) oder `"Notion"` oder `"User_geschaetzt"`.

### 2a.7 Mehrere Nutzungsarten

`alle_nutzungsarten[]` enthält bei MFH normalerweise zwei Einträge: `Ein/zweigeschossig` (Code 1) und `Misch-/Mehrgeschossig` (Code 2). **Primärwert für MFH = Misch-/Mehrgeschossig**, vom Scraper bereits als Top-Level `brw_eur_pro_qm` geliefert. Den anderen Wert nur erwähnen, wenn er stark abweicht (>20 % Differenz) und in Zone C als „BRW-Ein/zweigeschossig: <X> €/m² (zur Plausi)" notieren.

## 3. Berechnung / Logik

**3a) Tiefenstufen-Wahl:**

| Stufe | Eingang vorhanden | Output |
|-------|-------------------|--------|
| 1 | BRW + Grundstück + Anzahl WE + gleichmäßig verteilte Wohnflächen + ETW-Preis (Modul 1) | WE-Liste pauschal, Gebäudeanteil residual aus ETW-Verkaufspreis |
| 2 | + individuelle Wohnflächen je WE | WE-Liste detailliert |
| 3 | + Lage/Zimmer/Balkon/Keller je WE | WE-Liste komplett |
| 4 | + BGF + NHK_2010 + BKI-Index + Sachwertfaktor | Gebäudeanteil per Sachwertverfahren ImmoWertV Anlage 4 |
| 5 | + dokumentierter Sachwertfaktor aus GMB Stadt-Subpage | FA-konforme AfA-Bemessungsgrundlage |

**`tiefenstufe_max` = 5.** Default-Ziel: Stufe 3. Stufe 4/5 nur wenn User Sachwertverfahren-Inputs aktiv liefert.

**3b) Berechnung in fester Reihenfolge:**

**Grundsatz (Aufteiler-Basis, seit v1.5):** Der Gebäudeanteil wird **residual vom durchschnittlichen ETW-Verkaufspreis** gerechnet, NICHT vom MFH-Einkaufspreis. Grund: Beim Aufteiler werden die Wohnungen einzeln (teurer) verkauft; die AfA-Bemessungsgrundlage, die für den ETW-Käufer und damit für den Verkaufs-Cashflow maßgeblich ist, leitet sich vom Wohnungspreis ab. Der Bodenwert ist fix, der Preis je m² höher → der Gebäudeanteil steigt. Die MFH-Einkaufsbasis unterbewertet das Gebäude und ist für die ETW-Käufer-AfA nicht maßgeblich (sie wird nur nachrichtlich als Plausi in Zone C geführt).

```
Σ_wohnflaeche       = Σ modul_2.we_liste[].wohnflaeche_qm
bodenwert_eur       = brw_eur_pro_qm × grundstuecksflaeche_qm
bodenwert_je_qm_wfl = bodenwert_eur / Σ_wohnflaeche

# ETW-Verkaufspreis-Basis (Aufteiler) — Datenabhängigkeit Modul 1 → Modul 2:
etw_preis_je_qm     = modul_1.eur_per_qm.median
                      ↳ falls null: arithm. Mittel der vorhandenen (nicht-null) Portalwerte
                        in modul_1.eur_per_qm (homeday/immometrica/check24/interhyp/grundstuecksmarktbericht)
                      ↳ falls gar keiner vorhanden: AskUserQuestion nach ETW-€/m² (siehe 1a)
                        — KEIN stiller Rückfall auf die MFH-Einkaufsbasis.

# DEFAULT-Methode (Stufe 1–3), residual auf ETW-Verkaufspreis:
gebaeude_anteil_prozent = (etw_preis_je_qm − bodenwert_je_qm_wfl) / etw_preis_je_qm × 100

# Nachrichtlich für Zone C (Plausi, NICHT der State-Wert):
kaufpreis_eur              = modul_1.angebotspreis_eur
gebaeude_anteil_mfh_prozent = (kaufpreis_eur − bodenwert_eur) / kaufpreis_eur × 100

# Stufe 4–5 (Sachwertverfahren ImmoWertV Anlage 4) — bleibt MFH-KP-basiert (bekannte Limitierung,
#   für FA-Gutachten künftig pro Wohnung zu rechnen; NICHT Teil der v1.5-Umstellung):
#   NHK_2010_indexiert = NHK_2010 × (BKI_2026 / BKI_2010)
#   Alterswertminderung = (Alter / GND) × (1 − Modpunkte/20)
#   Gebäudesachwert_vorlaeufig = NHK_indexiert × BGF × (1 − Alterswertminderung) × Mod_Faktor
#   Vorlaeufiger_Sachwert = bodenwert + Gebäudesachwert_vorlaeufig
#   Marktangepasst = Vorlaeufiger × Sachwertfaktor
#   Gebäude_KP_Anteil = Kaufpreis × Gebäudesachwert_vorlaeufig / Vorlaeufiger_Sachwert
#   gebaeude_anteil_prozent = (Gebäude_KP_Anteil / Kaufpreis) × 100
```

In Stufe 4–5 sind die Modpunkte und GND noch nicht aus Modul 2 verfügbar (Modul 2 läuft nach Modul 1). Default-Annahmen `GND=80`, `Modpunkte=0`. Modul 2 kann später nachjustieren — kein Re-Schreiben von Modul 1, sondern Hinweis in Modul 2 Zone C.

**3c) Plausibilitäts-Prüfung:**

- `brw_eur_pro_qm > 0`, typisch 50–2000 €/m² in NRW.
- `etw_preis_je_qm > bodenwert_je_qm_wfl` — sonst wird `gebaeude_anteil_prozent ≤ 0` (bodenwert-lastige Lage): Hard-Warnung in Zone C, ETW-Preis-Quelle prüfen, kein Hard-Stop.
- `gebaeude_anteil_prozent` zwischen 50 % und 90 % → grün. Außerhalb → Warnung in Zone C, kein Hard-Stop. (Auf ETW-Basis liegt der Wert typisch höher als auf MFH-Basis — das ist gewollt.)
- Wohnfläche pro WE zwischen 10 und 250 m² (Schema-Grenze).
- Zimmer-Anzahl zwischen 1 und 8 (Schema-Grenze).
- Summe Wohnflächen WE-Liste muss zur Gesamt-Wohnfläche (falls separat angegeben) im Rahmen ±5 % passen. (Σ Wohnfläche geht direkt in `bodenwert_je_qm_wfl` ein — Schätzfehler hier verschiebt den Gebäudeanteil.)

## 4. Output erzeugen (Drei Zonen)

**Zone A — Daten-Block (pixel-identisch über alle Objekte):**

Block 1 — Objekt-Eckdaten:
```
| Position                           | Wert                                          |
|------------------------------------|-----------------------------------------------|
| Adresse                            | <objekt.adresse>                              |
| Stadt                              | <objekt.stadt>                                |
| Anzahl WE                          | <N>                                           |
| Grundstück                         | <grundstuecksflaeche_qm> m²                   |
| BRW                                | <brw_eur_pro_qm> €/m²                         |
| Bodenwert                          | <bodenwert_eur> €                             |
| Bodenwert je m² Wfl.               | <bodenwert_je_qm_wfl> €/m²                     |
| ETW-Verkaufspreis-Basis            | <etw_preis_je_qm> €/m² (Quelle: Modul 1)      |
| Kaufpreis (MFH-Einkauf, aus Modul 1)| <kaufpreis_eur> €                            |
| Gebäudeanteil %                    | <gebaeude_anteil_prozent> %                   |
| Methodik Gebäudeanteil             | Residual auf ETW-Verkaufspreis (Aufteiler-Basis) / Sachwertverfahren |
| Plausibilitäts-Check Gebäudeanteil | ok / warnung                                  |
```

Block 2 — WE-Liste:
```
| WE-Nr | Lage          | Wohnfläche m² | Zimmer | Balkon | Keller |
|-------|---------------|---------------|--------|--------|--------|
| 1     | EG            | 92.98         | 3      | ja     | ja     |
| …     | …             | …             | …      | …      | …      |
| Summe |               | <Σ qm>        |        |        |        |
```

Nicht-ermittelbare Werte: `"n/a"`, nicht weglassen.

**Zone B — Tiefenstufen-Deklaration (genau zwei Zeilen, byte-identisches Format):**

```
Tiefenstufe: <N> von 5 (<Begründung wenn nicht 5>)
Konfidenz: <hoch|mittel|niedrig>
```

**Zone C — Begründungs-Block (Struktur fix, Formulierung frei):**

1. **Wichtigste Annahmen** (max 5 Bullets) — z.B. „BRW aus BORIS.NRW PLZ 45356 Stand 2024", „WE-Flächen aus Exposé Seite 3", „ETW-Verkaufspreis-Basis <X> €/m² (Modul-1-Portal-Median)".
2. **Risiken / Unsicherheiten** (max 5 Bullets) — z.B. „WE 3 Wohnfläche nur geschätzt (Mieterliste fehlt)", „Gebäudeanteil bei 92 % → BRW evtl. zu niedrig".
3. **Empfehlung** (1–3 Sätze) — z.B. „Stufe 3 reicht für Modul 2/4. Vor Modul 5 BGF + Sachwertfaktor nachreichen für FA-konforme AfA."
4. **Plausi-Zeile MFH-Einkaufsbasis (Pflicht):** „Gebäudeanteil MFH-Einkaufsbasis (KP−Bodenwert)/KP = <gebaeude_anteil_mfh_prozent> % — nachrichtlich, für ETW-Käufer-AfA nicht maßgeblich." Zeigt den Kontrast zum State-Wert (ETW-Basis) und macht den Aufteiler-Hebel sichtbar.

**Excel-Transfer-Vorschau (Pflicht-Block nach Zone C):**

Tabelle der Zellen, die die Werte DIESES Moduls später (physischer Write erst in Modul 6 nach separater Freigabe) befüllen — Zell-Verträge aus `docs/excel_handoff.md`:

```
| Sheet!Zelle           | Wert                  |
|-----------------------|-----------------------|
| BESICHTIGUNG!B7       | <Σ Wohnfläche m²>     |
| BESICHTIGUNG!B9       | <Anzahl WE>           |
| MIETER!A8..A<7+N>     | 1 (Haus-Nr)           |
| MIETER!B8..B<7+N>     | <WE-Nr je Zeile>      |
| MIETER!C8..C<7+N>     | <Etage je Zeile>      |
| MIETER!D8..D<7+N>     | <Lage je Zeile>       |
| MIETER!E8..E<7+N>     | <Zimmer je Zeile>     |
| MIETER!F8..F<7+N>     | <Wohnfläche je Zeile> |
```

(BRW, Bodenwert, Gebäudeanteil haben kein Excel-Ziel — sie fließen in State + PDF Sektion 2/3.)

## 5. State persistieren

1. `modul_2`-Block bauen (gemäß `docs/state-schema.md`):
   ```json
   {
     "status": "<gruen|gelb|rot>",
     "tiefenstufe": <int 1-5>,
     "tiefenstufe_max": 5,
     "konfidenz": "<hoch|mittel|niedrig>",
     "brw_eur_pro_qm": <number>,
     "gebaeude_anteil_prozent": <number>,
     "we_liste": [
       {
         "we_nr": <int>,
         "lage_im_haus": "<string>",
         "wohnflaeche_qm": <number>,
         "zimmer_anzahl": <number>,
         "balkon": <bool>,
         "keller": <bool>,
         "mea_zaehler": <int — aus Teilungserklärung, sonst wohnflaeche_qm × 100>
       }
     ],
     "grundstuecksflaeche_qm": <number — die abgefragte Fläche aus Punkt 3 (seit v1.6 persistiert)>,
     "grundstuecksflaeche_quelle": {
       "quelle": "<Grundbuch|Flurkarte|ALKIS|Expose|User_geschaetzt>",
       "dokument": "<z.B. Grundbuch Bockum-Hövel Blatt 922, Bestandsverzeichnis lfd. Nr. 1>",
       "flurstueck": "<z.B. Flur 21, Flurstück 288 (13 a 41 qm)>",
       "konfidenz": "<hoch|mittel|niedrig>",
       "abgerufen_am": "<YYYY-MM-DD des Abdrucks/Abrufs>"
     },
     "mea_nenner": <int — Σ we_liste[].mea_zaehler bzw. Nenner der TE>,
     "mea_quelle": "<Teilungserklaerung|Wohnflaechenanteil_geschaetzt|User>",
     "garagen_gesamt": <int — Anzahl Garagen im Objekt (0 wenn keine)>,
     "stellplaetze_gesamt": <int — Anzahl Aussenstellplaetze (0 wenn keine)>,
     "garage_preis_eur": <number — Verkaufspreis je Garage, Marktansatz; weglassen wenn garagen_gesamt = 0>,
     "stellplatz_preis_eur": <number — Verkaufspreis je Stellplatz; weglassen wenn stellplaetze_gesamt = 0>,
     "garagen_preis_quelle": "<Expose|Portal|User|geschaetzt>",
     "brw_quelle": {
       "quelle": "<BORIS.NRW_auto|BORIS.NRW_manuell|Notion|User_geschaetzt>",
       "nutzungsart": "<z.B. Misch-/Mehrgeschossig>",
       "bodenrichtwertnummer": "<z.B. 12005>",
       "gemarkung": "<z.B. Eving oder null>",
       "ortsteil": "<z.B. Eving>",
       "stichtag": "<YYYY-MM-DD>",
       "abgerufen_am": "<YYYY-MM-DD>",
       "bestaetigte_adresse": "<von BORIS zurückgeliefert>",
       "geocoding_score": <number oder null>
     }
   }
   ```
   `brw_quelle` ist optional (Backwards-Compat mit alten state.json-Dateien), wird aber bei neuen Modul-1-Läufen IMMER gefüllt. Bei manuellem Fallback ohne BORIS-Aufruf: nur `quelle` + `abgerufen_am` sind Pflicht, Rest darf `null` sein.
2. `objekt.letzter_modul_lauf` auf `"modul_2"` setzen.
3. State schreiben (komplettes Objekt, nicht patchen).
4. `runs/<slug>/modul-1-output.md` mit Zonen A/B/C schreiben (Audit-Trail).
5. Validator-Lauf: `python tools/validate_state.py runs/<slug>/state.json`. Exit 0 = OK; ≠0 → state.json zurückrollen, Fehlertext an Orchestrator.

## 6. Self-Check (Pflicht vor Übergabe)

- [ ] Alle Pflichtfelder im Schema befüllt (status, tiefenstufe, tiefenstufe_max, konfidenz, brw_eur_pro_qm, gebaeude_anteil_prozent, we_liste)
- [ ] `we_liste` enthält mindestens 1 Eintrag, jeder Eintrag schemakonform
- [ ] `brw_eur_pro_qm > 0`, Wohnflächen im Bereich 10–250 m², Zimmer 1–8
- [ ] `grundstuecksflaeche_qm` gesetzt und `grundstuecksflaeche_quelle.quelle` benannt; bei `Expose` steht die Konfidenz auf höchstens `mittel` und Zone C nennt „Grundbuch/Flurkarte nachreichen"
- [ ] `mea_zaehler` bei jeder WE gesetzt, Σ `mea_zaehler` ≤ `mea_nenner`; bei `Wohnflaechenanteil_geschaetzt` steht der Hinweis „MEA geschätzt, TE liegt nicht vor" in Zone C
- [ ] `garagen_gesamt`/`stellplaetze_gesamt` gesetzt (auch `0`); bei Anzahl > 0 Preis je Einheit mit Quelle und User-Bestätigung; Σ `modul_5.we_mieten[].garagen_anzahl` ≤ `garagen_gesamt` (Validator)
- [ ] `gebaeude_anteil_prozent` auf ETW-Verkaufspreis-Basis gerechnet (Stufe 1–3, Formel 3b), zwischen 0 und 100 (Plausi-Warnung 50–90 ggf. in Zone C)
- [ ] ETW-Preis-Quelle dokumentiert (`modul_1.eur_per_qm.median` bzw. Portal-Mittel / User-Wert bei null)
- [ ] Zone-C-Plausi-Zeile „Gebäudeanteil MFH-Einkaufsbasis = <X> %" vorhanden
- [ ] `brw_quelle.quelle` gesetzt (einer der 4 Enum-Werte) — Audit-Trail für die BRW-Herkunft
- [ ] Excel-Transfer-Block ausgefüllt (siehe `docs/excel_handoff.md` Sheet MIETER + KALKU)
- [ ] `modul-1-output.md` erzeugt
- [ ] Validator-CLI exit 0

Bei rot → kein state.json-Schreiben, an Orchestrator zurück mit Fehlertext.

## 7. Chat-Visualisierung + Übergabe an Orchestrator (Pflicht-Reihenfolge)

**Schritt 1 — Pflicht-Visualisierung im Chat (NIE überspringen):** Den kompletten Zonen-Output 1:1 im Chat rendern — identisch zu dem, was in die Audit-Datei geschrieben wurde: Zone A (alle Blöcke als Markdown-Tabellen), Zone B, Zone C, Excel-Transfer-Vorschau. Grundsatz: **Alles, was später in PDF oder Excel landet, hat der User hier gesehen.** Ein Einzeiler ist NIE ausreichend — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

**Schritt 2 — Status-Zeile (NACH der Visualisierung):**
```
Modul 2 grün. WE-Liste mit <N> Einträgen, Gebäudeanteil <X> %. Werte in runs/<slug>/state.json, Audit in runs/<slug>/modul-1-output.md.
```

Die Weiter-Frage stellt der Orchestrator als klickbares `AskUserQuestion`-Gate — das Modul stellt selbst KEINE Freigabe-Frage.

============================================================

## Änderungen v1.6 (2026-09-11) gegenüber v1.5

- **Grundstücksfläche wird persistiert** (`grundstuecksflaeche_qm` + `grundstuecksflaeche_quelle`). Sie wurde seit jeher in Punkt 3 abgefragt und in Sektion 3 gerechnet, aber nie in den State geschrieben — der Reiter „Verkauf Cashflow" braucht sie jetzt je WE (Bodenwert = Fläche × BRW × MEA). Quellen-Rangfolge Grundbuch > Flurkarte/ALKIS > Exposé; Anlass: Rautenstrauchstraße 1, wo das Exposé „ca. 1.400 m²" nannte und das Grundbuch-Bestandsverzeichnis 1.341 m² (Flurstück 289 mit 59 m² war 1968 abgeschrieben).
- **Neuer Punkt 6: MEA je WE** (`we_liste[].mea_zaehler`, `mea_nenner`, `mea_quelle`). Ohne Teilungserklärung Wohnflächenanteil als Schätzung, gekennzeichnet und überschreibbar.
- **Neuer Punkt 7: Garagen/Stellplätze als Verkaufs-Assets** (`garagen_gesamt`, `stellplaetze_gesamt`, `garage_preis_eur`, `stellplatz_preis_eur`, `garagen_preis_quelle`) — Preis je Einheit mit Quelle und Gate; Modul 6 schreibt je WE Anzahl × Preis in `Verkauf Cashflow!Q/R` (André, 2026-09-11: „die Preise kommen aus dem Aufteiler-Modul, nicht per Hand").
- Self-Check um beide Punkte erweitert. Schema/Validator/Doku: Commit `efa298e`.

## Änderungen v1.5 (2026-07-01) gegenüber v1.4

- **Gebäudeanteil auf ETW-Verkaufspreis-Basis (Aufteiler-Basis).** Die Default-Methode (Stufe 1–3) in Sektion 3b rechnet den Gebäudeanteil jetzt residual vom durchschnittlichen ETW-Verkaufspreis je m² Wohnfläche statt vom MFH-Einkaufspreis: `gebaeude_anteil_% = (etw_preis_je_qm − bodenwert_je_qm_wfl) / etw_preis_je_qm × 100`. Grund: Beim Aufteiler werden die Wohnungen einzeln teurer verkauft; die für den ETW-Käufer und den Verkaufs-Cashflow maßgebliche AfA-Bemessungsgrundlage leitet sich vom Wohnungspreis ab. Der fixe Bodenwert bei höherem €/m² → höherer Gebäudeanteil (Beispiel: 47 % MFH-Basis → 67 % ETW-Basis).
- **ETW-Preis-Quelle + Fallback-Kaskade:** `modul_1.eur_per_qm.median` → Mittel der vorhandenen Portalwerte → `AskUserQuestion` (neue Weiche in 1a). Kein stiller Rückfall auf die MFH-Basis. Datenabhängigkeit Modul 1 → Modul 2 in Sektion 1 + 3b dokumentiert.
- **Zone A** um „Bodenwert je m² Wfl." + „ETW-Verkaufspreis-Basis" erweitert; Methodik-Zeile auf „Residual auf ETW-Verkaufspreis (Aufteiler-Basis)". **Zone C** neue Pflicht-Plausi-Zeile mit dem MFH-Einkaufsbasis-Gebäudeanteil (nachrichtlich).
- **Sachwertverfahren (Stufe 4/5) unverändert** — bleibt MFH-KP-basiert; für FA-Gutachten künftig pro Wohnung zu rechnen (bekannte Limitierung, nicht Teil dieser Umstellung).
- **Kein Schema-/Validator-/Excel-Vertrag-Change:** `modul_2.gebaeude_anteil_prozent` (number, 0–100) und `Verkauf Cashflow!C10` (Modul 6 schreibt durch) bleiben. Es ändert sich nur, wie der Wert entsteht. Referenz: `plans/2026-07-01-modul2-wohnungs-basis-gebaeudeanteil.md`.

## Änderungen v1.4 (2026-06-11) gegenüber v1.3

- **Gate-Härtung + Pflicht-Visualisierung** nach Datteln-Lauf 2026-06-11 (`plans/2026-06-11-orchestrator-gate-haertung-visualisierung.md`): Sektion 7 von „Eine Zeile" auf Pflicht-Reihenfolge Visualisierung (Zonen A/B/C 1:1 + Excel-Transfer-Vorschau) → Status-Zeile umgestellt; neue Sektion 1a Entscheidungs-Weichen (> ±5 % nie autonom auflösen, `AskUserQuestion` mit Empfehlung als erster Option); neuer Pflicht-Block „Excel-Transfer-Vorschau" in Sektion 4; Status-Zeile auf echte Modul-Nummer (2) korrigiert. Audit-Dateiname `modul-1-output.md` bewusst unverändert (Bestands-Vertrag).

## Änderungen v1.3 (2026-05-20) gegenüber v1.2

- **Neuer Sub-Punkt 2a.3 „Adress-Bestätigung"** als Pflicht-Stop VOR dem BRW-Pre-Fill. User pickt + validiert die geocodete Adresse selbst — analog zu seinem manuellen BORIS-UI-Workflow (2× ArrowDown + Enter, dann Augen-Check). Kein Auto-Pick, auch nicht bei single-hit + Score≥2.5.
- **Neuer Sub-Pfad 2a.3a „Andere Adresse"** ruft Scraper mit `--mode geocode-only` auf und zeigt features[0..4] als gleichwertige Auswahl. Nach User-Pick: erneuter `--mode full`-Lauf mit den Adress-Komponenten aus dem gewählten Kandidaten.
- **Alte Sub-Punkte 2a.3 / 2a.4 / 2a.5 / 2a.6** umnummeriert zu 2a.4 / 2a.5 / 2a.6 / 2a.7. Inhalte unverändert.
- **Scraper-Migration auf offizielle OGC WMS GetFeatureInfo** (`wms.nrw.de/boris/wms_nw_brw`, INFO_FORMAT=application/geo+json). Der bisherige Reverse-Engineering-Endpoint `getBRWbyCoords.json` ist ersetzt durch zwei WMS-Aufrufe je Nutzungsart-Layer (17 = Misch-/Mehrgeschossig MFH-Primär, 20 = Ein/zweigeschossig). CLI-Schnittstelle + JSON-Output-Schema unverändert. Plan-Test-Cases gegen WMS verifiziert: Deutsche Str. 59 = 330/12005, Prosperstr. 59 = 250/17209.
- **Hintergrund Adress-Bestätigung:** 2026-05-19 lieferte Auto-Pick + Validierungs-Kaskade silently falsche BRW für „Prosperstraße 59, 45356 Essen" (Geocoder fand „Erdwegstr. 59, 45356 Essen" im Score-Bereich 2.04). Bug-Fix war zunächst Heuristik (Straßen-Match-Normalisierung), Symptom-Bekämpfung. User-Diagnose: „Es ist einfach. Aber du machst es dir selbst kaputt, weil du dich im Kreis drehst." Richtiger Fix: User-Confirm an Stelle der Maschinen-Heuristik; Heuristik bleibt als Sicherheitsnetz im Scraper.

## Änderungen v1.2 gegenüber v1.1

- **Neue Sektion 2a — Auto-BRW-Lookup** via `tools/m01_boris_brw.py` (REST gegen `gis-rest.nrw.de`, kein Browser). Pre-Fill-Pattern: User bestätigt Vorschlag oder überschreibt.
- **Punkt 2 (BRW-Eingabe)** verweist auf 2a; Pre-Fill aus BORIS statt blanker Eingabe.
- **Neuer State-Block `modul_2.brw_quelle`** mit Audit-Metadaten (`quelle`, `nutzungsart`, `bodenrichtwertnummer`, `gemarkung`, `ortsteil`, `stichtag`, `abgerufen_am`, `bestaetigte_adresse`, `geocoding_score`). Optional für Backwards-Compat, Pflicht bei neuen Läufen.
- **Self-Check** um `brw_quelle.quelle`-Check erweitert.
- **Zone C "Wichtigste Annahmen"** sollte bei Auto-Lookup explizit die Bodenrichtwertnummer + Stichtag aus BORIS nennen (statt nur "BRW aus BORIS.NRW").

Referenzen: `plans/2026-05-20-modul1-adress-bestaetigung.md`, `plans/2026-05-19-modul1-boris-scraper-hardening.md`, `tools/_boris_snapshots/DISCOVERY.md` §8 (REST-Schema).
