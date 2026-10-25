---
name: aufteiler-modul-5-miete
description: Modul 5 der Aufteiler-Analyse — Mietsituation (Mietspiegel, §558-Heberecht, Mietsubvention). Tiefenstufen 1–6. Seit 2026-05-22 mit autonomem Wohnlage-Reasoning (Konfidenz-Gate ≥ 70 %, Quellen Notion → WebFetch → WebSearch → Plausi-Cross-Check). Wird ausschließlich vom aufteiler-Orchestrator aufgerufen. Seit 2026-05-25: Mietspiegel-DB-Stadt-Fail spawnt Sub-Skill `aufteiler-marktdaten-fallback` mode=mietspiegel — Stadt-Webseite-Quellen-Kaskade, extrahiert Basis-€/m² + Kappung + Mietpreisbremse + Typ, schreibt DB-Zeile, returnt Werte. Bei Konfidenz <70 % weiterhin `AskUserQuestion`-Fallback (mit LLM-Empfehlung als 1. Option). Seit 2026-06-11 Pflicht-Visualisierung des kompletten Zonen-Outputs + Excel-Transfer-Vorschau im Chat vor dem Orchestrator-Gate; Entscheidungs-Weichen > ±5 % (z.B. Mietspiegel-Baualtersgruppe) nie autonom auflösen. Seit 2026-06-25 Ist-Schutz der Kaltmiete SOLL als Excel-Automatik (MIETER!R = MAX(Ist, Mietspiegel-Soll)) — Ist-Mieten über Mietspiegel werden im Verkauf-Cashflow nicht gesenkt. Seit 2026-09-11 erhebt und persistiert das Modul je WE die Felder der Verkaufs-Kalkulation (Sektion 2 Punkte 4–7): Ist-Miete als Sollstellungs-Betrag, Leerstand (immer gesetzt), Einzug, letzte Mieterhöhung (HV-Liste vor Erhöhungsschreiben, ohne Beleg leer), Reach-Time, Garagen/Stellplätze getrennt (Anzahl + Miete), Hausgeld-Paar oder Bewirtschaftungsquote, Kappungsgrenze und § 559-Umlage — alles für den Reiter „Verkauf Cashflow" (Vorwärtsrechnung je Wohnung nach CRM-Logik).
---

# Modul 4 — Mietsituation

Pro WE: Ist-Miete, Sollmiete (Mietspiegel-Algorithmus), Mietspiegel-Obergrenze, §558-Heberecht, Mietsubvention bis Sollmiete erreicht ist. Architektur **Option C** (aus altem XML v2.0): M6 = VOR Aufteiler-Sanierung; Aufteiler-Massnahmen 2026 fließen NICHT in den Mietspiegel-Mittelwert, sondern in Excel `MIETER!T4` als §559-Modernisierungsumlage. Mietsubvention ist eine **separate Cashflow-Position**, NICHT im Reno-Block (Asset-Trennung).

## 1. State laden (Pflicht — erste Aktion)

1. Vom Orchestrator bekomme ich `objekt_slug`. Pfad: `runs/<objekt_slug>/state.json`.
2. State einlesen mit `Read`.
3. Pflicht-Vorgänger-Felder prüfen. Wenn etwas fehlt → STOPP, Antwort an Orchestrator:
   `"Modul 4: Pflichtfeld <pfad> fehlt. Bitte Modul 1 erneut laufen lassen."`

**Pflicht-Vorgänger:** `modul_2.we_liste` (mindestens 1 WE).

Modul 3 ist nicht zwingend Vorgänger (Modul 4 kann theoretisch unabhängig laufen), aber bei Vollanalyse läuft 3 vor 4.

## 1a. Entscheidungs-Weichen während des Modullaufs (Pflicht-Regel)

Trifft das Modul auf eine echte Weiche — eine Annahme-Entscheidung mit Effekt > ±5 % auf ein Modul-Ergebnis (Sollmieten, §558-Heberecht, Subventions-Summe) — SOFORT `AskUserQuestion` stellen, mit der eigenen Empfehlung als erster Option (Suffix „(Empfehlung)"). Solche Weichen NIE autonom mit der eigenen Empfehlung auflösen — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

Typische Weichen in diesem Modul:
- **Mietspiegel-Baualtersgruppe** bei Baujahr nahe einer Klassengrenze oder bei Kernsanierungs-Umklassifizierung — die Basis-€/m²-Wahl wirkt auf JEDE Sollmiete
- Wohnlage bei Konfidenz < 70 % (bereits `AskUserQuestion`-Fallback in 2.5, bleibt)
- Mietspiegel-Fallback-Werte bei Konfidenz < 70 (bereits geregelt in Sektion 2.1, bleibt)
- Kappungsgrenze 15 vs. 20 % (stadtabhängig — bei Unsicherheit fragen, nicht NRW-Default annehmen)
- Ausstattungs-Zuschläge 4.3–4.10, wenn die Beleg-Lage mehrdeutig ist und der Zuschlag-Stack > ±5 % auf die Sollmiete wirkt

Ohne Weichen läuft das Modul autonom durch — endet aber IMMER in der Pflicht-Visualisierung (Sektion 7) + dem Freigabe-Gate des Orchestrators.

## 2. Inputs erheben

Per `AskUserQuestion` einzeln:

1. **Mietspiegel-Daten aus Notion-DB** (Data-Source `collection://8b000923-d5ee-45a4-8f6a-e7f3bf81f20e` — Mietspiegel NRW) für Stadt `objekt.stadt`.

   **Bei Treffer:** Werte aus DB-Zeile + Body lesen.

   **Bei Stadt nicht in DB:** Sub-Skill `aufteiler-marktdaten-fallback` aufrufen (`--interaktiv 1` weil Modul-4 immer Orchestrator-Modus):

   ```bash
   cd c:\meine-projekte\Immobilien\Aufteiler\tools\marktdaten-fallback
   python orchestrator.py --mode mietspiegel \
     --stadt "<objekt.stadt>" \
     --baujahr <modul_3.baujahr> \
     --interaktiv 1 \
     --slug "<objekt_slug>"
   ```

   Output verarbeiten:
   - Konfidenz ≥ 70: Werte verwenden (`eur_per_qm` als Basis-€/m², `zusatzfelder` für Kappung/Mietpreisbremse/Typ). MCP-Call(s) aus `action`-Lines ausführen. `state.modul_5.mietspiegel_fallback_quelle` Sub-Block befüllen.
   - Konfidenz < 70: `AskUserQuestion` mit LLM-Empfehlung aus `result.begruendung` als 1. Option + Quellen-Trail in der Frage zitiert. Pattern aus Wohnlage-Reasoning (Abschnitt 2.5).

   Erwartete Felder aus DB-Zeile (Treffer) bzw. Fallback-Output:
   - Basis-Wert €/m² je Baujahres-Klasse (aus Mietspiegel-Tabelle)
   - Kappungsgrenze in % (NRW Standard 15 oder 20 %)
   - Mietpreisbremse ja/nein
   - **Lage-Korrektur:** NICHT mehr hier abfragen — wird in Abschnitt 2.5 autonom recherchiert.
2. **Ist-Miete pro WE** — eine Zeile pro WE, Format: `<WE-Nr>: <Ist-Miete €/Monat kalt>`. Beispiel: `1: 380.40`. Quelle ist der **Sollstellungs-Betrag** der Hausverwaltung (Mieterliste/Sollzusammenstellung, Zeile „Sollstellung Miete") bzw. `objektdaten.json` → `we_liste[].ist_miete_eur_monat`. Der Euro-Betrag wird als `ist_miete_eur_pro_monat` persistiert; `ist_miete_eur_pro_qm` ist nur der daraus abgeleitete Quotient (umgekehrt verliert `€/m² × Fläche` Cents). Dazu je WE zwei Pflicht-Merker: **`leerstand`** (immer setzen, auch `false`; bei Ist-Miete 0 zwingend `true` — der Validator lehnt `0` mit `leerstand=false` ab) und **`mieter_seit`** (Einzugsdatum aus der HV-Liste, Spalte „Einzug"; leer nur, wenn kein Beleg).
3. **Bestand-Sanierungsstand** — aus `modul_3.mod_score` und altem-XML-Logik: User kann Bestand-Aufzählung pro Gewerk hinzufügen für Mietspiegel-Zuschläge 4.3–4.10. Default: keine Zuschläge, wenn nichts belegt (analog R02 Modul 3).
4. **Letzte Mieterhöhung je WE** (seit 2026-09-11) — Quelle 1: HV-Sollzusammenstellung, Spalte **„letzte Erh."**; Quelle 2: Erhöhungsschreiben im Mieterordner (Datum „tritt in Kraft", z.B. `09.1 Mietverträge/<Mieternr>/Letzte Mieterhöhung/`). Bei Widerspruch gewinnt das **jüngere** Datum (das abgelegte Schreiben ist oft das ältere). Ohne Beleg bleibt das Feld **leer** — das Einzugsdatum ist KEIN Ersatz, es steht separat in `mieter_seit`. Persistiert als `letzte_mieterhoehung` (`YYYY-MM-DD`); Modul 6 schreibt es als Datum nach `MIETER!I`, wo der Reiter „Verkauf Cashflow" daraus Sperrfrist und Subventionsdauer ableitet.
5. **Garagen und Stellplätze je WE** (seit 2026-09-11, Asset-Trennung) — getrennt erheben: `garagen_anzahl` / `stellplaetze_anzahl` und `garage_miete_eur_pro_monat` / `stellplatz_miete_eur_pro_monat` aus der HV-Liste (Zeile „Sollstellung Garagenmiete", Zuordnung über „/ GA n" bei der Einheit — nicht über die Reihenfolge der Beträge im Listenkopf; Anlass: Rautenstrauchstraße 1, wo `objektdaten.json` die Garage GA 4 der WE 10 statt WE 3 zuordnete). Modul 6 schreibt die **Summe beider Mieten** nach `MIETER!K` (das ist die Mietspalte, `K28 = SUM`; nie eine Stückzahl dorthin).
6. **Hausgeld je WE** (seit 2026-09-11) — nur, wenn ein Wirtschaftsplan/eine Hausgeldabrechnung je Einheit vorliegt: `hausgeld_nicht_umlagefaehig_eur_pro_monat` (Gesamt der nicht umlagefähigen Kosten) **und** `hausgeld_ruecklage_eur_pro_monat` (der darin enthaltene Rücklagen-Anteil, nicht addieren) — beide oder keines (Validator). Ohne Wirtschaftsplan (Regelfall vor der Teilung) beide leer lassen; das Excel rechnet dann mit Verwaltung `C62` + RND-Rücklage `C64`. Alternativ eine Prozent-Schätzung `bewirtschaftungsquote_schaetzung` (Anteil der Nettokaltmiete) — **nie** zusammen mit dem Euro-Wert.
7. **Reach-Time, Kappungsgrenze, § 559** (seit 2026-09-11) — die in Sektion 3 je WE berechnete Reach-Time (Monate bis Ziel-Sollmiete über die Kappungsstufen) wird als `reach_time_monate` persistiert. **Ziel-Sollmiete** (Zone A „Ziel €/m²") ist der Mittelwert aus `sollmiete_eur_pro_qm` (Mittelwert + Zuschläge) und `mietspiegel_obergrenze_eur_pro_qm`; Modul 6 schreibt sie als `Verkauf Cashflow!AI` (`soll_miete`), die Subvention je Wohnung rechnet dort gegen genau diesen Wert (`0`, wenn keine Subvention — der Validator prüft die Kopplung). Die verwendete Kappungsgrenze als `kappungsgrenze` (0,15 NRW-Default; 0,20, wo die MietSchVO nicht greift), die § 559-Umlage als `paragraph_559_umlage_prozent` (`0`, wenn keine — heute nur als `MIETER!T4` erwähnt). Alle drei speisen den Reiter „Verkauf Cashflow" direkt.

**Wichtig — Option C:**
- Aufteiler-Massnahmen 2026 aus `modul_4.massnahmen_liste` werden für Mietspiegel-Zuschläge IGNORIERT. Sie wirken nur über `MIETER!T4` (Excel rechnet §559-Umlage). Modul 4 setzt T4 NICHT selbst, prüft aber `modul_4.summen.modernisierung_netto_eur` als Hinweis.
- **Doppelrechnung-Safety-Check** (Pflicht vor State-Write): kein Aufteiler-2026-Element aus `modul_4` als Mietspiegel-Zuschlag in `modul_5.we_mieten[]` eingeflossen.

## 2.5 Wohnlage-Reasoning (autonom, seit 2026-05-22)

**Ziel:** Die Wohnlage-Klasse für die Adresse `objekt.adresse, objekt.stadt` selbst ermitteln, OHNE User-Frage solange Konfidenz ≥ 70 %.

Pflicht-Reihenfolge der Quellen — billigste zuerst. Jeder Treffer wird in `quellen_trail` aufgenommen.

**Quelle 1 — Notion-DB Mietspiegel NRW** (Page-ID `8b000923-d5ee-45a4-8f6a-e7f3bf81f20e`):
- Stadt-Page suchen. Prüfen, ob ein "Wohnlagen-Verzeichnis" oder "Straßenverzeichnis" als Sub-Page existiert.
- Bei direktem Treffer Straße → Klasse: Eintrag `{typ:"notion", quelle:"<page-titel>", ergebnis:"<klasse>"}` in `quellen_trail`, Konfidenz +50.

**Quelle 2 — WebFetch auf bekannte Stadt-Mietspiegel-URLs:**
- Essen: `https://www.essen.de/leben/wohnen/mietspiegel.de.html`
- Oberhausen: `https://www.oberhausen.de/de/index/rathaus/buergerservice/dienstleistungen/mietspiegel.php`
- Dortmund: `https://www.dortmund.de/themen/bauen-und-wohnen/mietspiegel/`
- Bochum: `https://www.bochum.de/Wohnen-und-Bauen/Mietspiegel`
- Düsseldorf: `https://www.duesseldorf.de/wohnungsamt/mietspiegel.html`

WebFetch nutzen, Prompt: "Welche Wohnlage hat die Straße `<Straße ohne Hausnummer>` laut Mietspiegel-Straßenverzeichnis? Wenn Liste mit Lage-Klassen + prozentualen Korrekturen erkennbar, alle Klassen + ihre Korrekturen mit ausgeben."

- Treffer mit konkretem Lage-Eintrag → `{typ:"webfetch", quelle:"<url>", ergebnis:"<klasse>"}`, Konfidenz +30.
- Falls kein Straßen-Treffer aber Mietspiegel-Tabelle mit Klassen + Korrekturen geliefert → Klassen-Liste für Quelle 4 merken, Konfidenz +5.

**Quelle 3 — WebSearch tief (mehrere Anfragen):**
- Anfrage 1: `"<Straße> <Stadt> Wohnlage Mietspiegel"`
- Anfrage 2: `"<Stadtteil> <Stadt> Mietspiegel Lage Einstufung"`
- Anfrage 3: `"<Stadtteil> <Stadt> Wikipedia"` (sozioökonomischer Kontext)
- Anfrage 4 (nur wenn 1-3 leer): `"<Stadt> Wohnlagen-Verzeichnis"`

Jeden brauchbaren Treffer in `quellen_trail` aufnehmen: `{typ:"websearch", quelle:"<url>", ergebnis:"<extrahierter befund>"}`.
- Pro überzeugendem Treffer Konfidenz +10, gegenläufige Treffer −10.

**Quelle 4 — Plausibilisierungs-Cross-Check über Bestandsmieten:**
- Aus Abschnitt 2.2 vorliegende Ist-Mieten Median berechnen.
- Wenn Quelle 2 oder 3 eine Mietspiegel-Tabelle mit Basis-€/m² je Klasse geliefert hat:
  - Erwartete €/m² je Klasse rechnen: `basis × (1 + lage_korrektur/100)`
  - Ist-Median mit erwarteten Werten vergleichen, Best-Match-Klasse als Plausi.
- Übereinstimmung mit anderen Quellen → Konfidenz +15; Widerspruch → −20.
- `quellen_trail`-Eintrag: `{typ:"plausi_bestandsmieten", quelle:"ist-mieten-median", ergebnis:"<median> €/m² → <klasse> best-match"}`.

**Konfidenz-Gate:**

- `konfidenz_score = max(0, min(100, Σ aus Quellen))`
- Wenn `konfidenz_score >= 70`:
  - `modul_5.wohnlage.klasse`, `.lage_korrektur_prozent`, `.konfidenz_score`, `.quellen_trail`, `.begruendung` in State schreiben.
  - `user_bestaetigt = false`.
  - KEINE User-Frage.
- Wenn `konfidenz_score < 70`:
  - User per `AskUserQuestion` fragen, Optionen aus den im Mietspiegel gefundenen Klassen bilden.
  - LLM-Empfehlung als ERSTE Option mit Suffix "(Empfehlung — Konfidenz X %)".
  - Begründung in der Frage zitieren.
  - Nach User-Antwort: `klasse` + `lage_korrektur_prozent` aus User-Wahl, `konfidenz_score` unverändert lassen, `user_bestaetigt = true`.

**`begruendung`-Format (2–4 Sätze, knapp, für PDF-Export):**

> "Wohnlage `<klasse>` (`<lage_korrektur_prozent>` %) gewählt auf Basis: `<kurzer Quellen-Hinweis>`. Cross-Check mit Bestandsmieten (Median `<X>` €/m²) bestätigt Einstufung. `<Optional: 1 Satz Restunsicherheit.>`"

Beispiel Beisenstr. 52:

> "Wohnlage VI (−1,9 %) gewählt auf Basis essen.de/mietspiegel-Straßenverzeichnis und Stadtteil-Profil Katernberg-Süd (ehemalige Bergmannssiedlung, niedriges Mietniveau). Cross-Check mit Bestandsmieten (Median 6,9 €/m²) bestätigt Einstufung im unteren Bereich. Wechsel zu V Referenz unwahrscheinlich, da keine UNESCO-Welterbe-Nähe."

**Wichtig — Sprach-Generizität:** Diese Logik ist NICHT Essen-spezifisch. Stadt-Mietspiegel benennen Klassen unterschiedlich (Essen: "V/VI/VII", Dortmund: "einfach/mittel/gut", Oberhausen: numerisch). Die Klasse wird 1:1 so übernommen, wie sie im jeweiligen Mietspiegel benannt ist (Feld `klasse` ist string, nicht enum).

## 3. Berechnung / Logik

**3a) Tiefenstufen-Wahl:**

| Stufe | Eingang vorhanden | Output |
|-------|-------------------|--------|
| 1 | Ist-Mieten + Anzahl WE | Sollmiete als pauschaler Median des Stadtteils |
| 2 | + Mietspiegel-Basis pro Baujahr-Klasse | Sollmiete pro WE basisbasiert |
| 3 | + Lage-Korrektur | + Lage-Anpassung |
| 4 | + Bestand-Ausstattungs-Zuschläge (4.3–4.9) | + Ausstattungs-Zuschläge |
| 5 | + Bestand-Modernisierungs-Zuschläge mit Jahr (4.10) | + Modernisierungs-Zuschläge BESTAND |
| 6 | + Markt-Validation (Immometrika/IS24-Median + Vermarktungsdauer + Inseratsanzahl) | + Markt-Adjustment |

`tiefenstufe` 1–6, Schema-Max 6. Default-Ziel: Stufe 4.

**3b) Berechnung pro WE in fester Reihenfolge:**

```
# Schritt 1: Basis-Sollmiete €/m² aus Baujahr-Klasse (Mietspiegel)
sollmiete_basis_eur_pro_qm = lookup(mietspiegel_db, stadt, baujahres_klasse(modul_3.baujahr))

# Schritt 2: Lage-Korrektur addieren
sollmiete_mit_lage = sollmiete_basis_eur_pro_qm + lage_korrektur

# Schritt 3: Bestand-Ausstattungs-Zuschläge (4.3–4.9) — NUR aus BESTAND, nicht aus modul_4!
zuschlaege_bestand = Σ ausstattungs_zuschlaege_belegt
sollmiete_mit_zuschlaegen = sollmiete_mit_lage + zuschlaege_bestand

# Schritt 4: Bestand-Modernisierungs-Zuschläge 4.10 mit Jahr (nur aus modul_3 Bestand!)
mod_zuschlaege = Σ mod_zuschlaege_bestand_mit_jahr
sollmiete_eur_pro_qm = sollmiete_mit_zuschlaegen + mod_zuschlaege

# Schritt 5: Mietspiegel-Obergrenze (üblicher Cap +18 % auf Spanne)
mietspiegel_obergrenze_eur_pro_qm = sollmiete_eur_pro_qm × 1.18

# Schritt 6: §558-Heberecht pro WE
# Kappungsgrenze (k) wirkt: alte Miete × (1+k), aber gecapped auf sollmiete
neue_miete_eur_pro_monat = min(
    ist_miete_eur_pro_qm × wohnflaeche_qm × (1 + k),
    (mietspiegel_obergrenze_eur_pro_qm + sollmiete_eur_pro_qm) / 2 × wohnflaeche_qm
)
paragraph_558_heberecht_eur = max(0, neue_miete_eur_pro_monat − ist_miete_eur_pro_monat)
```

**3c) Mietsubvention berechnen (Step 8 aus altem XML, deterministische Stufen-Formel):**

```
# Pro WE:
k = kappungsgrenze (z.B. 0.15 für NRW)
SOLL_we = mietspiegel_obergrenze_eur_pro_qm × wohnflaeche_qm
IST_we = ist_miete_eur_pro_qm × wohnflaeche_qm

# Stufen:
#   Stufe 0: Anlauf 3 Monate, Stufenmiete = IST_we
#   Stufe n>0: Dauer 36 Monate (Kappungsgrenze-Intervall NRW), Stufenmiete = IST × (1+k)^n, gecapped auf SOLL_we
# n_voll = AUFRUNDEN(LOG(SOLL_we / IST_we) / LOG(1+k) − 1; 0)

n_voll = ceil(log(SOLL_we / IST_we) / log(1+k) − 1)
reach_time_monate = 3 + n_voll × 36

# Subvention je Stufe:
for n in 0..n_voll:
    stufenmiete_n = min(IST_we × (1+k)**n, SOLL_we)
    diff_n = SOLL_we − stufenmiete_n
    dauer_mo = 3 if n == 0 else 36
    subv_stufe_n = diff_n × dauer_mo

subv_we_eur = Σ subv_stufe_n
subv_we_pro_monat_eur = subv_we_eur / reach_time_monate    # Durchschnitt über Reach-Time
```

**Wichtig — Schema-Mapping:**

Das Schema (state-schema.md) hat ein einzelnes Feld `mietsubvention_eur_pro_monat` pro WE (kein Stufen-Detail). Im State wird der **Durchschnitt über Reach-Time** geschrieben — der detaillierte Stufenplan landet im `modul-4-output.md` Zone A.

```
mietsubventionen_summe_eur_pro_monat = Σ subv_we_pro_monat_eur über alle WE
mietsubventionen_total_eur           = Σ (subv_we_pro_stufe_eur × stufen_dauer_monate) über alle Stufen + WE
                                       (Einmal-Pauschale über die gesamte Reach-Time → VERKAUFSMATRIX!Y27, negativ)
```

**3d) Plausibilitäts-Prüfung:**

- `ist_miete_eur_pro_qm`, `sollmiete_eur_pro_qm`, `mietspiegel_obergrenze_eur_pro_qm` ≥ 0.
- Wenn `IST_we >= SOLL_we`: `mietsubvention_eur_pro_monat = 0`, Hinweis „Miete bereits ≥ Soll".
- Wenn `SOLL_we / IST_we > 3.0`: Plausi-Warnung in Zone C („extreme Reach-Time, ggf. Mieterwechsel-Pfad realistischer").
- Wenn Reach-Time > 20 J: Hinweis in Zone C.
- **Doppelrechnung-Check:** kein `modul_4.massnahmen_liste`-Eintrag als Mietspiegel-Zuschlag in `we_mieten`-Berechnung verwendet.

**3e) Status-Ableitung:**

- Alle WE valide + Subvention im 5-stelligen €-Bereich: `status = "gruen"`
- Reach-Time > 15 J oder Subvention > 100k EUR-Range: `status = "gelb"`
- Mietsubvention nicht berechenbar (Y fehlt für ≥1 WE): `status = "rot"`

## 4. Output erzeugen (Drei Zonen)

**Zone A — Daten-Block (PIXEL-IDENTISCHE Reihenfolge, DREI Pflicht-Blöcke):**

**Block 1 — Mietsubventionen pro WE (Cashflow-Position für VERKAUFSMATRIX, NICHT für Reno):**
```
| WE-Nr | Wohnfläche m² | Ist-Miete €/m² | Sollmiete €/m² | Subvention €/Monat | Reach-Time Mo |
|-------|---------------|----------------|----------------|--------------------|---------------|
| 1     | 92.98         | 4.09           | 8.65           | 220.50             | 183           |
| …     | …             | …              | …              | …                  | …             |
| Σ     |               |                |                | <Σ €/Mo>           |               |
```

**Block 2 — Aktuelle Miete vs. Sollmiete (pro WE):**
```
| WE-Nr | Ist €/m² | Soll €/m² | Mietspiegel-Obergrenze €/m² | Delta €/m² | Delta % |
|-------|----------|-----------|------------------------------|------------|---------|
| 1     | 4.09     | 7.33      | 8.65                         | +3.24      | +79%    |
| …     | …        | …         | …                            | …          | …       |
```

**Block 3 — §558-Heberecht (pro WE):**
```
| WE-Nr | §558-Heberecht €/Monat | Aktiv? | Hinweis |
|-------|--------------------------|--------|---------|
| 1     | 245.00                   | ja     | Kappung 15 % greift |
| …     | …                        | …      | …       |
```

Nicht-ermittelbare Werte: `"n/a"`, nicht weglassen.

**Zone B:**
```
Tiefenstufe: <N> von 6 (<Begründung wenn nicht 6>)
Konfidenz: <hoch|mittel|niedrig>
```

**Zone C:**

1. **Wichtigste Annahmen** (max 5 Bullets) — z.B. „Mietspiegel Essen 2024, Baujahres-Klasse 1949–1977", „Lage Essen-Dellwig: mittel +0.20 €/m²", „Kappungsgrenze NRW 15 %".
2. **Risiken / Unsicherheiten** (max 5 Bullets) — z.B. „Reach-Time WE 3 mit 18 J grenzwertig", „Markt-Median nicht validiert (Tiefenstufe 5 statt 6)".
3. **Empfehlung** (1–3 Sätze) — z.B. „Subvention 5J über Reach-Time geplant. Vor Modul 5: Immometrika-Lookup für Markt-Validation (Stufe 6)."

**Wohnlage-Recherche (Pflicht-Block, seit 2026-05-22):**

Direkt nach "Empfehlung" als eigener Mini-Block einfügen:

```
**Wohnlage:** <klasse> (<lage_korrektur_prozent> %)
**Konfidenz:** <konfidenz_score> %<, vom User bestätigt>   ← Suffix nur wenn user_bestaetigt=true
**Quellen:**
- <typ_1>: <quelle_1> → <ergebnis_1>
- <typ_2>: <quelle_2> → <ergebnis_2>
- ...
**Begründung:** <begruendung-Text 1:1 aus state.json>
```

Maximal 6 Zeilen, knapp halten. Wenn `quellen_trail` mehr als 4 Einträge hat: nur die 3 stärksten zeigen + Suffix `"... (<N> weitere geprüft, siehe state.json)"`.

**Pflicht-Hinweis (immer in Zone C ergänzen):**

```
Asset-Trennung: Mietsubvention NICHT in modul_4.massnahmen_liste, sondern hier in modul_4
+ VERKAUFSMATRIX-Extra-Spalte. Mietpreisbremse-Hinweis: <ja/nein> für <Stadt>.
Aufteiler-Massnahmen 2026 wirken via Excel MIETER!T4 §559-Umlage, NICHT im
Mietspiegel-Mittelwert M6 (Option C, kein Doppelansatz).
```

**Excel-Transfer-Vorschau (Pflicht-Block nach Zone C):**

Tabelle der Zellen, die die Werte DIESES Moduls später (physischer Write erst in Modul 6 nach separater Freigabe) befüllen — Zell-Verträge aus `docs/excel_handoff.md`:

```
| Sheet!Zelle           | Wert                                          |
|-----------------------|-----------------------------------------------|
| MIETER!H8..H<7+N>     | <Einzug je WE, Datum>                         |
| MIETER!I8..I<7+N>     | <letzte Mieterhöhung je WE, Datum oder leer>  |
| MIETER!J8..J<7+N>     | <Kaltmiete IST €/Monat je WE, Sollstellung>   |
| MIETER!K8..K<7+N>     | <Garagen- + Stellplatzmiete €/Monat je WE>    |
| MIETER!T4             | <§ 559-Umlage, 0 wenn keine>                  |
| MIETER!Y8..Y<7+N>     | <Mietspiegel-Obergrenze €/m² je WE>           |
| MIETER!M6             | <gewichteter Mietspiegel-Mittelwert €/m²>     |
| MIETER!P6             | <Kappungsgrenze, z.B. 0.15>                   |
| BESICHTIGUNG!B33      | <IST-JNKM €/Jahr>                             |
| BESICHTIGUNG!B34      | <Kappungsgrenze, z.B. 0.15>                   |
| VERKAUFSMATRIX!Y27    | <Mietsubvention-Total über Reach-Time, **NEGATIV**> |
```

**Ist-Schutz Kaltmiete SOLL (Excel-Automatik, seit 2026-06-25):** Die Spalte `MIETER!R` (Kaltmiete SOLL) rechnet per Formel `MAX(Ist-Kaltmiete, Mietspiegel-Soll)`. Liegt eine Ist-Miete über dem Mietspiegel, wird sie im Reiter „Verkauf Cashflow" (zieht `MIETER!R`) **nicht** nach unten korrigiert. Das Modul schreibt `R` nicht selbst (reine Formel); konsistent zur Plausi-Regel `IST_we >= SOLL_we` → Subvention 0 (Sektion 3d).

## 5. State persistieren

1. `modul_5`-Block bauen (gemäß Schema):
   ```json
   {
     "status": "<gruen|gelb|rot>",
     "tiefenstufe": <int 1-6>,
     "tiefenstufe_max": 6,
     "konfidenz": "<hoch|mittel|niedrig>",
     "we_mieten": [
       {
         "we_nr": <int>,
         "ist_miete_eur_pro_qm": <number>,
         "sollmiete_eur_pro_qm": <number>,
         "mietspiegel_obergrenze_eur_pro_qm": <number>,
         "paragraph_558_heberecht_eur": <number>,
         "mietsubvention_eur_pro_monat": <number>,
         "ist_miete_eur_pro_monat": <number — Sollstellungs-Betrag, Pflicht seit 2026-09-11>,
         "leerstand": <bool — immer setzen, auch false>,
         "mieter_seit": "<YYYY-MM-DD oder null>",
         "letzte_mieterhoehung": "<YYYY-MM-DD oder null — nur mit Beleg>",
         "reach_time_monate": <int — 0 bei Subvention 0>,
         "garagen_anzahl": <int>,
         "stellplaetze_anzahl": <int>,
         "garage_miete_eur_pro_monat": <number>,
         "stellplatz_miete_eur_pro_monat": <number>,
         "hausgeld_nicht_umlagefaehig_eur_pro_monat": <number — nur mit Wirtschaftsplan, sonst weglassen>,
         "hausgeld_ruecklage_eur_pro_monat": <number — der darin enthaltene Anteil; Paar-Pflicht>,
         "bewirtschaftungsquote_schaetzung": <number 0–0,6 — Alternative zum Euro-Paar, nie beides>
       }
     ],
     "kappungsgrenze": <number — 0.15 oder 0.20, wie in Sektion 3 verwendet>,
     "paragraph_559_umlage_prozent": <number — 0 wenn keine Umlage>,
     "mietsubventionen_summe_eur_pro_monat": <number = Σ über we_mieten>,
     "mietsubventionen_total_eur": <number = Σ subv_we über alle Stufen/Reach-Time → VERKAUFSMATRIX!Y27 (negativ eingetragen)>,
     "begruendung_je_we": {
       "1": "<kurz: Lage, Zuschläge, Auffälligkeiten>",
       "…": "…"
     },
     "wohnlage": {
       "klasse": "<z.B. VI / mittel / 3>",
       "lage_korrektur_prozent": <-20..20>,
       "konfidenz_score": <0..100>,
       "quellen_trail": [
         { "typ": "<notion|webfetch|websearch|plausi_bestandsmieten>",
           "quelle": "<URL/Page-ID/optional>",
           "ergebnis": "<extrahierter Befund>" }
       ],
       "begruendung": "<2–4 Sätze, min 20 Zeichen>",
       "user_bestaetigt": <bool, true wenn User unter 70 % Konfidenz gefragt wurde>
     }
   }
   ```

   Hinweis: `wohnlage` ist Schema-optional. Wenn das LLM keine Klasse ermitteln kann UND der User keine Bestätigung gegeben hat (z.B. Modul wurde nur teilweise gefahren), Feld weglassen statt mit Nullwerten füllen.
2. **Asset-Trennung-Pflichtcheck**: Mietsubvention NICHT in `modul_4.massnahmen_liste`. (Schema-Validator + Modul-3-Self-Check enforced.)
3. **Doppelrechnung-Check**: kein `modul_4`-Eintrag als Mietspiegel-Zuschlag verwendet.
4. `objekt.letzter_modul_lauf` auf `"modul_5"` setzen.
5. State schreiben.
6. `runs/<slug>/modul-4-output.md` mit Zonen A/B/C schreiben (alle drei Pflicht-Blöcke).
7. Validator-Lauf: `python tools/validate_state.py runs/<slug>/state.json`. Exit 0 = OK; ≠0 → state.json zurückrollen.

## 6. Self-Check (Pflicht vor Übergabe)

- [ ] Alle Pflichtfelder befüllt (status, tiefenstufe, tiefenstufe_max, konfidenz, we_mieten, mietsubventionen_summe_eur_pro_monat, begruendung_je_we)
- [ ] `we_mieten` enthält genau `len(modul_2.we_liste)` Einträge
- [ ] Jeder `we_mieten[]`-Eintrag schemakonform (6 Pflichtfelder + Felder der Verkaufs-Kalkulation)
- [ ] `ist_miete_eur_pro_monat` bei jeder WE aus der Sollstellung (Euro), `leerstand` bei jeder WE gesetzt (auch `false`), `reach_time_monate` bei jeder WE gesetzt (0 bei Subvention 0)
- [ ] `letzte_mieterhoehung` nur mit Beleg (HV-Liste „letzte Erh." oder Erhöhungsschreiben), sonst `null`; `mieter_seit` aus der HV-Liste
- [ ] Garagen/Stellplätze über die „/ GA n"-Zuordnung der Einheit geprüft, Summe der Garagenmieten = Listenkopf der HV
- [ ] Hausgeld-Paar entweder vollständig (Gesamt + enthaltene Rücklage) oder ganz weggelassen; nicht zusammen mit `bewirtschaftungsquote_schaetzung`
- [ ] `kappungsgrenze` und `paragraph_559_umlage_prozent` persistiert (→ `BESICHTIGUNG!B34`, `MIETER!P6`, `MIETER!T4`)
- [ ] `mietsubventionen_summe_eur_pro_monat == Σ we_mieten[].mietsubvention_eur_pro_monat`
- [ ] **Asset-Trennung**: `modul_4.massnahmen_liste` enthält weiterhin KEIN `subvention`/`rücklage` (Modul 4 darf den Reno-Block nicht anfassen)
- [ ] **Doppelrechnung-Check**: kein Aufteiler-2026 als Mietspiegel-Zuschlag in `we_mieten`
- [ ] `modul_3.rnd_frozen` unverändert
- [ ] Drei Pflicht-Tabellen in `modul-4-output.md` in fixer Reihenfolge (Subventionen → Miete-Vergleich → §558)
- [ ] Excel-Transfer-Block (MIETER!M6, P6, Y8:Y, VERKAUFSMATRIX!Y27) im Output dokumentiert
- [ ] **Wohnlage-Block** (seit 2026-05-22): `modul_5.wohnlage` befüllt mit 5 Pflichtfeldern, `konfidenz_score ≥ 70` ODER `user_bestaetigt = true`; `quellen_trail` enthält mind. 1 Eintrag aus Notion/WebFetch/WebSearch/Plausi
- [ ] **Wohnlage-Recherche-Block** in Zone C des `modul-4-output.md` vorhanden (Klasse, Konfidenz, Quellen, Begründung)
- [ ] Validator-CLI exit 0

Bei rot → kein state.json-Schreiben, an Orchestrator zurück.

## 7. Chat-Visualisierung + Übergabe an Orchestrator (Pflicht-Reihenfolge)

**Schritt 1 — Pflicht-Visualisierung im Chat (NIE überspringen):** Den kompletten Zonen-Output 1:1 im Chat rendern — identisch zu dem, was in die Audit-Datei geschrieben wurde: Zone A (alle drei Pflicht-Blöcke: Subventionen → Miete-Vergleich → §558 als Markdown-Tabellen), Zone B, Zone C inkl. Wohnlage-Recherche-Block + Pflicht-Hinweis, Excel-Transfer-Vorschau. Grundsatz: **Alles, was später in PDF oder Excel landet, hat der User hier gesehen.** Ein Einzeiler ist NIE ausreichend — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

**Schritt 2 — Status-Zeile (NACH der Visualisierung):**
```
Modul 5 grün. <N> WE, Subventions-Summe <X> €/Monat. Werte in runs/<slug>/state.json, Audit in runs/<slug>/modul-4-output.md.
```

Die Weiter-Frage stellt der Orchestrator als klickbares `AskUserQuestion`-Gate — das Modul stellt selbst KEINE Freigabe-Frage.

---

## Änderungen

- **2026-09-11** — Felder der Verkaufs-Kalkulation (Umbau Reiter „Verkauf Cashflow" auf CRM-Objektlisten-Logik): Sektion 2 Punkt 2 erweitert (Ist-Miete als Sollstellungs-Betrag `ist_miete_eur_pro_monat`, Pflicht-Merker `leerstand` und `mieter_seit`), neue Punkte 4–7 (letzte Mieterhöhung mit Quellen-Rangfolge, Garagen/Stellplätze getrennt, Hausgeld-Paar oder Quote, Reach-Time/Kappung/§ 559 persistieren). State-JSON, Self-Check und Excel-Transfer-Vorschau nachgezogen. Klarstellung in Punkt 7: die Ziel-Sollmiete (Zone A „Ziel €/m²") ist der Mittelwert aus `sollmiete_eur_pro_qm` und `mietspiegel_obergrenze_eur_pro_qm` — Modul 6 schreibt sie als `Verkauf Cashflow!AI`. Anlass: Rautenstrauchstraße 1 — `MIETER!J` verlor Cents durch `€/m² × Fläche`, die Garage GA 4 war der falschen WE zugeordnet, Kappung 0,20 und Reach-Time standen nirgends im State. Schema/Validator/Tests: Commit `efa298e`.

- **2026-06-25** — Ist-Schutz Kaltmiete SOLL (`plans/2026-06-25-excel-vkcf-ist-miete-schutz.md`): Doku-Hinweis in Sektion 4 (Excel-Transfer-Vorschau) ergänzt. Keine Modul-Logik-Änderung — der Schutz sitzt als Excel-Formel in `MIETER!R` (`MAX(Ist, Mietspiegel-Soll)`), der Reiter „Verkauf Cashflow" zieht `R`. Behebt: Bestandsmieten über Mietspiegel wurden in der Verkaufs-Rückrechnung auf Mietspiegel-Niveau gesenkt.

- **2026-06-11** — Gate-Härtung + Pflicht-Visualisierung nach Datteln-Lauf (`plans/2026-06-11-orchestrator-gate-haertung-visualisierung.md`): Sektion 7 von „Eine Zeile" auf Pflicht-Reihenfolge Visualisierung (Zonen A/B/C 1:1 + Excel-Transfer-Vorschau) → Status-Zeile umgestellt; neue Sektion 1a Entscheidungs-Weichen (> ±5 % nie autonom — Mietspiegel-Baualtersgruppe, Kappungsgrenze, Zuschlag-Stack; Wohnlage-<70 %-Gate bleibt); neuer Pflicht-Block „Excel-Transfer-Vorschau" in Zone C; Status-Zeile auf echte Modul-Nummer (5) korrigiert. Audit-Dateiname `modul-4-output.md` bewusst unverändert (Bestands-Vertrag).

- **2026-05-22** — Autonomes Wohnlage-Reasoning (Abschnitt 2.5) eingeführt. Statt User-Frage führt das Modul jetzt 4-stufige Recherche durch (Notion → WebFetch auf Stadt-Mietspiegel-URLs → WebSearch tief → Plausi-Cross-Check über Bestandsmieten). Konfidenz-Schwelle 70 — darunter Fallback auf `AskUserQuestion` mit LLM-Empfehlung als erste Option. Neues optionales State-Sub-Objekt `modul_5.wohnlage` mit `klasse`, `lage_korrektur_prozent`, `konfidenz_score`, `quellen_trail`, `begruendung`, `user_bestaetigt`. Output-Erweiterung: neuer "Wohnlage-Recherche"-Block in Zone C des `modul-4-output.md`. PDF-Konsumption: Modul-5 Sektion 10.2 zeigt aufgelösten Eintrag (siehe `aufteiler-modul-5-deal-bewertung/SKILL.md`). Plan: `plans/2026-05-22-modul4-wohnlage-llm-reasoning.md`.
