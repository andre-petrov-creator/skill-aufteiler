---
name: aufteiler-modul-6-deal-bewertung
description: Modul 6 der Aufteiler-Analyse — Deal-Bewertung mit PDF-Export und Excel-Befüllung. Konsumiert State aus Modul 1–5. Wird ausschließlich vom aufteiler-Orchestrator aufgerufen. Seit 2026-06-11 Excel-Schutz verschärft — vollständige Werte-Vorschau (Zelle | Wert | Quell-Modul) im Chat VOR der Excel-Freigabe-Frage; Pauschal-Freigaben ("analysiere alles durch") gelten NICHT als Bestätigung für Excel oder PDF. Seit 2026-06-25 schreibt das Modul AfA (C9) + Gebäudeanteil (C10) als Werte in den Reiter "Verkauf Cashflow" (ex "VK_CF"). Seit 2026-06-26 zusätzlich die Instandhaltungsrücklage (C64, €/m²/Jahr aus RND-Staffel 10/14/18), die die komponentenbasierte C8-Formel (Verwaltung + Rücklage, nur nicht-umlagefähige Vermieterkosten) speist; Rücklagen-Topf-Sensitivität liegt als Excel-Sektion im selben Reiter. Seit 2026-09-11 ist die Excel-Befüllung das Werkzeug `tools/export_excel.py` (`--dry-run` = Pflicht-Werte-Vorschau); das Template ist Fassung V2 (`AUFTEILER_TPL_V2`): der Reiter „Verkauf Cashflow" rechnet vorwärts je Wohnung (Regler €/m² → Kaufpreis, Cashflow vor/nach Steuern, Faktor, Rendite; Hausgeld/Rücklage getrennt; Gebäudeanteil je WE aus BRW × Grundstück × MEA; Kontrollspalten 100 %/109,3 %), das Werkzeug schreibt dafür den Datenblock je WE aus Modul 1/2/5 und lässt `MIETER!K` als Formel-Spiegel stehen. Vertrag: `docs/excel_handoff_vkcf.md`.
---

# Modul 5 — Deal-Bewertung

Aggregations- und Export-Modul. Konsumiert `modul_1` … `modul_5` aus `runs/<slug>/state.json`, rechnet **nichts** selbst neu (außer Platzhalter-Score), erzeugt PDF + befüllt Excel-Template. **Nie automatisch in Vollanalyse-Sequenz** — nur bei expliziter User-Anfrage.

Score-Logik ist **Platzhalter** — wird durch echte Methodik ersetzt sobald sie aus dem parallelen Optimierungs-Prozess kommt. State-Feld `modul_6.bewertungs_score` bleibt stabil, nur die Befüllungs-Logik wird getauscht (siehe `plans/2026-05-12-score-logik-modul-5-offen.md`).

## 1. State laden (Pflicht — erste Aktion)

1. Vom Orchestrator bekomme ich `objekt_slug`. Pfad: `runs/<objekt_slug>/state.json`.
2. State einlesen mit `Read`.
3. Pflicht-Vorgänger-Felder prüfen. Wenn etwas fehlt → STOPP, Antwort an Orchestrator:
   `"Modul 5: Pflichtfeld <pfad> fehlt. Bitte Modul <M> erneut laufen lassen."`

**Pflicht-Vorgänger:** alle Module 0–4 mit `status` gesetzt:
- `modul_1.status`
- `modul_2.status` + `modul_2.we_liste`
- `modul_3.status` + `modul_3.rnd_jahre` + `modul_3.rnd_frozen=true`
- `modul_4.status` + `modul_4.summen`
- `modul_5.status` + `modul_5.we_mieten`

Wenn eines fehlt: STOPP, exakte Fehlermeldung an Orchestrator (welches Modul nachholen).

## 1a. Entscheidungs-Weichen während des Modullaufs (Pflicht-Regel)

Trifft das Modul auf eine echte Weiche — eine Annahme-Entscheidung mit Effekt > ±5 % auf ein Ergebnis in PDF oder Excel — SOFORT `AskUserQuestion` stellen, mit der eigenen Empfehlung als erster Option (Suffix „(Empfehlung)"). Solche Weichen NIE autonom mit der eigenen Empfehlung auflösen — auch nicht bei „Vollanalyse"/„alles durchlaufen"-Aufträgen.

Typische Weichen in diesem Modul:
- Bewirtschaftungs-Rücklage €/m²/Jahr — C64 wird aus der RND-Staffel (RND≥40→10, 20–40→14, <20→18) gesetzt und speist die komponentenbasierte C8-Formel; bei erkennbar abweichender Kostenstruktur (frisch saniert, Aufzug) C64 anpassen statt Staffel-Default
- Bestand-Heizungs-Rücklage / Stichtags-Jahr Heizungs-Pflichttausch, wenn sie die Rücklagen-Entwicklung sichtbar kippen

Ohne Weichen läuft das Modul autonom durch — Excel und PDF haben zusätzlich IMMER ihre eigenen Freigabe-Stops (Sektion 2/3b/3c).

## 2. Inputs erheben

**Keine User-Inputs.** Modul 5 konsumiert ausschließlich `state.json` und das Excel-Template.

Optional (falls nicht im State, dann User-Frage einmalig):
- **Bewirtschaftungs-Rücklage €/m²/Jahr** (Default aus RND-Staffel: RND≥40→10, 20–40→14, <20→18). Speist die C8-Formel im Reiter "Verkauf Cashflow" (C8 = (Verwaltung + Rücklage)/Nettokaltmiete, nur Vermieterkosten — Versicherung + Grundsteuer sind umlagefähig und bleiben draußen).
- **Bestand-Heizungs-Rücklage** € (Default 0, wenn unbekannt).
- **Stichtags-Jahr für Heizungs-Pflichttausch** (Default `baujahr_heizung + 30`, sonst `2032` als Konvention).

Bei Default-Verwendung: in Zone C unter „Annahmen" notieren, dass User-Werte ausstehen.

Reihenfolge der User-Freigaben:
1. Nach Score-Berechnung: vollständige Excel-Werte-Vorschau im Chat (Sektion 3b Schritt 1), DANN `AskUserQuestion` "Excel mit diesen Werten befüllen?"
2. Nach Excel-Save: `AskUserQuestion` "PDF generieren?"
Keine der beiden Aktionen darf ohne explizite, im jeweiligen Moment erteilte Bestätigung ausgeführt werden.

**Eine frühere Pauschal-Freigabe (z.B. „analysiere alles durch", „Vollanalyse", „von A bis Z") gilt NICHT als Bestätigung für Excel oder PDF.** Die Bestätigung zählt nur als Antwort auf die konkrete `AskUserQuestion` mit sichtbarer Werte-Vorschau.

## 3. Berechnung / Logik

**3a) Platzhalter-Score (Ampel-Aggregation aus Modul-Status + Konfidenz):**

```python
base_score = 70
for m in [modul_1, modul_2, modul_3, modul_4, modul_5]:
    if m["status"] == "rot":
        base_score -= 10
    elif m["status"] == "gelb":
        base_score -= 5
    konf = m.get("konfidenz", "mittel")
    if konf == "niedrig":
        base_score -= 5
    elif konf == "mittel":
        base_score -= 2
bewertungs_score = max(0, min(100, base_score))
```

**Hinweis im Skill-Output (Zone C Pflicht):**
```
HINWEIS: Diese Score-Logik ist ein PLATZHALTER. Echte Score-Methodik
folgt — siehe plans/2026-05-12-score-logik-modul-5-offen.md. Nur die
Befüllung wird ausgetauscht; State-Feld modul_6.bewertungs_score bleibt.
```

**3b) Excel-Befüllung (NUR nach Werte-Vorschau + expliziter Freigabe):**

**Schritt 1 — Vollständige Werte-Vorschau (Pflicht VOR der Frage):** ALLE Zellen, die der Excel-Code schreiben wird, als Tabelle im Chat rendern — inklusive RENO-Mengen und Excel-Comments:

```
| Sheet!Zelle        | Wert                          | Quell-Modul  |
|--------------------|-------------------------------|--------------|
| BESICHTIGUNG!B6    | <adresse>                     | Orchestrator |
| BESICHTIGUNG!B7    | <Σ Wohnfläche>                | Modul 2      |
| BESICHTIGUNG!B8    | <Baujahr>                     | Modul 3      |
| BESICHTIGUNG!B9    | <Anzahl WE>                   | Modul 2      |
| BESICHTIGUNG!B13   | <Angebotspreis>               | Modul 1      |
| BESICHTIGUNG!B34   | <Kappungsgrenze>              | Modul 5      |
| MIETER!A8..F<7+N>  | <WE-Stamm je Zeile>           | Modul 2      |
| MIETER!G8..G<7+N>  | <Mietername je WE>            | objektdaten.json |
| MIETER!H8..I<7+N>  | <Einzug / letzte Erhöhung je WE, als Datum> | Modul 5 |
| MIETER!J8..J<7+N>  | <Kaltmiete IST je WE, Sollstellungs-Betrag> | Modul 5 |
| MIETER!K8..K<7+N>  | <Garagen- + Stellplatzmiete je WE> | Modul 5 |
| MIETER!T4          | <§ 559-Umlage, 0 wenn keine>  | Modul 5      |
| MIETER!Y8..Y<7+N>  | <Mietspiegel-Obergrenze je WE>| Modul 5      |
| MIETER!M6 / P6     | <Mittelwert / Kappung>        | Modul 5      |
| KALKU!I13..I17     | <Portalpreise €/m²>           | Modul 1      |
| RENO!I<zeile> je M.| <Menge je Massnahme>          | Modul 4      |
| RENO!I104 / K104   | <WEG-Teilung>                 | Modul 4      |
| RENO!F105/I105/K105 | RND-Gutachten (600/WE × N WE) | Modul 4      |
| VERKAUFSMATRIX!Y27 | <Mietsubvention total, NEGATIV>| Modul 5      |
| Verkauf Cashflow!C9  | <AfA-Satz, z.B. 0.025>      | Modul 3      |
| Verkauf Cashflow!C10 | <Gebäudeanteil, z.B. 0.75>  | Modul 2      |
| Verkauf Cashflow!C64 | <Rücklage €/m², 10/14/18 aus RND> | Modul 3 (RND) |
| Verkauf Cashflow Parameterblock (Objekt: Grundstück m², BRW, MEA-Nenner; Käuferprofil: AfA-Satz Std., Gebäudeanteil Std.; Zellen aus `tools/vkcf_vertrag.py`) | <Werte aus Modul 2/3> (Template V2) | Modul 2/3 |
| Verkauf Cashflow!L/J/G/H/I/Q/R<3+i> | <Regler €/m² = M1-Median, MEA-Zähler, Leerstand, Garagen/Stellplätze je WE (Anzahl und Preis = Anzahl × Preis je Einheit)> (V2) | Modul 1/2/5 |
| Verkauf Cashflow!AI/AK/AL/AM/AS<3+i> | <Ziel-Sollmiete, Subvention Ø, Garagen-/Stellplatzmiete, Reach-Time je WE> (V2) | Modul 5 |
| Verkauf Cashflow!AW/AX/AZ<3+i> | <Bewirtschaftungsquote bzw. Hausgeld-Paar je WE, nur wenn erhoben> (V2) | Modul 5 |
| Comments (H10/A40/Y27) | <AfA, Score, Subvention>  | Modul 3/6/5  |
```

WE-Zeilen dürfen pro WE als eine Tabellen-Zeile zusammengefasst werden, aber JEDER Wert muss sichtbar sein. Keine Zelle schreiben, die nicht in der Vorschau stand.

**Schritt 2 — `AskUserQuestion` (Pflicht):** "Excel mit diesen Werten befüllen? Datei wird überschrieben." — Optionen: "Ja, befüllen" / "Werte korrigieren" / "Nein, überspringen".

**Schritt 3 — Korrektur-Schleife:** Wählt der User "Werte korrigieren" (oder nennt konkrete Korrekturen):
1. Korrektur ins Quell-Feld in `state.json` übernehmen (State bleibt Source of Truth — nie nur die Excel-Zelle ändern), Validator laufen lassen (exit 0).
2. Bei gefrorenen/berechneten Werten (z.B. `rnd_jahre`, Sollmieten-Formel-Ergebnisse): nicht direkt patchen — an Orchestrator zurückmelden, dass Modul N mit Korrektur erneut laufen muss.
3. Aktualisierte Vorschau-Tabelle erneut rendern, `AskUserQuestion` erneut stellen. Schleife bis "Ja, befüllen" oder "Nein".

Nur wenn der User "Ja, befüllen" auf die AKTUELLE Vorschau klickt → Excel-Code ausführen. Eine Pauschal-Freigabe aus früheren Nachrichten gilt NICHT (Sektion 2).

**3c) PDF generieren (NUR nach expliziter Freigabe):**

AskUserQuestion PFLICHT vor PDF-Build: "PDF-Report generieren?" — Optionen: "Ja, generieren" / "Nein, nur Excel reicht".
Nur wenn User "Ja" → PDF-Code ausführen. Auch hier gilt: eine frühere Pauschal-Freigabe („analysiere alles durch") ist KEINE PDF-Bestätigung.

Vor Build: PDF-Layout-Regeln aus Skill `aufteiler-pdf-export` laden und R1–R13 anwenden. Form-Skill liefert reportlab-Code-Bausteine, Modul 5 nutzt sie direkt.

PDF-Struktur (Reihenfolge wie alt `archive/modul_5_verdict.xml`):

- **Cover**: Headline „Analyse zur Aufteiler-Kalkulation <Straße>", Stammdaten, Hebel-Kaskade-Chart, GO/GRENZ/STOP-Verdict-Box (abgeleitet aus `bewertungs_score`)
- **Sektion 1** Stammdaten (aus `modul_1`)
- **Sektion 2** Bodenrichtwert (aus `modul_2.brw_eur_pro_qm`)
- **Sektion 3** Gebäudewert (aus `modul_2.gebaeude_anteil_prozent`) + Donut-Chart
- **Sektion 4** WE-Liste + IST-vs-SOLL-Chart (aus `modul_2.we_liste` + `modul_5.we_mieten`)
- **Sektion 5.1** Modernisierungsstand (aus `modul_3.begruendung` + `modul_4.massnahmen_liste`)
- **Sektion 5.2** Energieeffizienz (aus `modul_4.enev_klasse`)
- **Sektion 5.3** Massnahmen 2026 + GIK-Donut (aus `modul_4.summen`)
- **Sektion 6** RND + AfA-Gauge (aus `modul_3.afa_korridor_prozent`)
- **Sektion 7.1** Mietspiegel-Berechnung pro WE (aus `modul_5.we_mieten`)
- **Sektion 7.2** M6-Mittelwert + Markt-Validation
- **Sektion 8.1–8.4** Mietsubvention pro WE Stufentabellen + Aggregat-Treppe (aus `modul_5.mietsubventionen_summe_eur_pro_monat`)
- **Sektion 8.5** Bewirtschaftungs-Einschätzung: Komponenten Verwaltung (35 €/WE/Mo) + Instandhaltungsrücklage (C64 €/m²/Jahr aus RND-Staffel) → resultierende C8-Quote (nur Vermieterkosten; Versicherung/Grundsteuer umlagefähig = ausgeklammert). Rücklage in drei Größen (€/m²/J, €/J, € über 10 J) + Hinweis auf die Rücklagen-Topf-Sensitivität im Excel (Reiter "Verkauf Cashflow" Z.73–87: WEG-Topf 0–50k → Quote & max. VK-Preis)
- **Sektion 9** Risiko-Heatmap + Risiko-Tabelle (10 Standard-Risiken aus altem XML, parametrisiert)
- **Sektion 10.1** Verdict-Box (aus `bewertungs_score`) + Marge-Sensitivitäts-Chart
- **Sektion 10.2** Pflicht-Schritte-Checkliste vor Notartermin. Mietspiegel-Wohnlage-Item ist seit 2026-05-22 ein **aufgelöster Eintrag**, wenn `modul_5.wohnlage` existiert UND (`konfidenz_score >= 70` ODER `user_bestaetigt == true`). Render-Regel:
  - **Aufgelöst** (Eintrag hat `[OK]` als ASCII-Marker, kein Emoji): `[OK] Mietspiegel-Wohnlage: <klasse> (<lage_korrektur_prozent> %), Konfidenz <konfidenz_score> %` + darunter eingerückt `Begründung: <begruendung 1:1>` + `Quellen: <quellen_trail typ-zusammenfassung kommagetrennt>`.
  - **Offen** (Backward-Compat für States ohne `wohnlage`-Feld): wie bisher Pflicht-To-do.
  - Layout-Regeln aus `skills/aufteiler-pdf-export/SKILL.md` zwingend (Spaltenbreiten, Word-Wrap, KeepTogether, kein Emoji).
- **Sektion 11** Anhang: Quellen + BFH-Pflichthinweis + MPB-Hinweis + Disclaimer

PDF-Pfad: `runs/<slug>/Aufteiler_<Straßenkurz>_<YYYY-MM-DD>.pdf` (Straßenkurz-Ableitung format-aware: bei neuem Slug-Format `<Straße>_<Hausnr>` aus dem ersten Komma-Segment, z.B. `Vestische_Straße_250`; bei Legacy-kebab-case erste zwei Bindestrich-Blöcke, z.B. `Prosperstr-59`).

PDF-Build via `python -c` oder `python skripts/build_pdf_modul5.py runs/<slug>/state.json` (Skript optional, falls Skill-Inline-Build unhandlich wird; in Phase 4 zunächst inline).

**Excel-Befüllung (gemäß `docs/excel_handoff.md`):**

**Seit 2026-09-11 ist die Befüllung ein Werkzeug:** `python tools/export_excel.py "runs/<slug>/state.json" --dry-run` erzeugt die Werte-Vorschau (Sheet!Zelle | Wert | Quelle) für Schritt 1; nach der Freigabe schreibt derselbe Aufruf ohne `--dry-run` (Ziel: `runs/<slug>/Kalkulation_<Straßenkurz>.xlsx`, abweichend per `--out`; bestehende Datei nur mit `--force`, dann mit Backup; Schreiben über Temp-Datei + `os.replace`). Der Code-Block darunter ist die Referenz, aus der das Werkzeug portiert wurde — Änderungen gehören ins Werkzeug, nicht in den Block.

Excel-Template `template/Kalkulation_Aufteiler_mit_VK_CF.xlsx` wird zu `runs/<slug>/Kalkulation_<Straßenkurz>.xlsx` kopiert. Schreib-Reihenfolge:

```python
from openpyxl import load_workbook
from openpyxl.comments import Comment
import shutil, json
from pathlib import Path

state = json.load(open(state_path, encoding="utf-8"))
slug = state["objekt"]["slug"]

# Format-Detection: Komma-Substring nur im neuen Format vorhanden
if ", " in slug:
    # Neues Adress-Format: "Vestische Straße 250, 46145 Oberhausen-Sterkrade"
    strasse_kurz = slug.split(", ")[0].replace(" ", "_")
    # → "Vestische_Straße_250"
else:
    # Legacy kebab-case: "prosperstr-59-essen-dellwig"
    strasse_kurz = "-".join(slug.split("-")[:2])
    # → "prosperstr-59"

src = Path("template/Kalkulation_Aufteiler_mit_VK_CF.xlsx")
dst = Path(f"runs/{slug}/Kalkulation_{strasse_kurz}.xlsx")
shutil.copyfile(src, dst)

wb = load_workbook(dst)

# ===== 1. BESICHTIGUNG (Eingabe-Maske; KALKU/VK_CF zieht sich daraus) =====
besichtigung = wb["BESICHTIGUNG"]
besichtigung["B6"]  = state["objekt"]["adresse"]
besichtigung["B7"]  = sum(we["wohnflaeche_qm"] for we in state["modul_2"]["we_liste"])
besichtigung["B8"]  = state["modul_3"]["baujahr"]
besichtigung["B9"]  = len(state["modul_2"]["we_liste"])
besichtigung["B13"] = state["modul_1"]["angebotspreis_eur"]
besichtigung["B34"] = 0.15  # NRW-Default Kappungsgrenze

# ===== 2. MIETER (WE-Stamm aus M1, IST aus M4, Y aus M4) =====
def etage_aus_lage(lage):
    """'EG' -> 'EG', 'OG_links'/'OG_rechts' -> '1.OG' (default), 'DG_*' -> 'DG'.
    Wenn '2.OG_*' im Lage-String: gibt '2.OG'. Heuristik."""
    L = lage.lower()
    if l := L.startswith("eg"):
        return "EG"
    if "dg" in L or "dachgeschoss" in L:
        return "DG"
    if "2.og" in L or "2_og" in L or "og2" in L:
        return "2.OG"
    if "og" in L:
        return "1.OG"
    return lage  # Fallback wie gegeben

def lage_aus_lage(lage):
    L = lage.lower()
    if "links" in L:
        return "links"
    if "rechts" in L:
        return "rechts"
    return ""

mieter = wb["MIETER"]
N = len(state["modul_2"]["we_liste"])
for i, we in enumerate(state["modul_2"]["we_liste"]):
    row = 8 + i
    mieter[f"A{row}"] = 1  # Haus-Nr (Single-Haus-MFH; bei Mehrhaus später anpassen)
    mieter[f"B{row}"] = we["we_nr"]
    mieter[f"C{row}"] = etage_aus_lage(we["lage_im_haus"])
    mieter[f"D{row}"] = lage_aus_lage(we["lage_im_haus"])
    mieter[f"E{row}"] = we["zimmer_anzahl"]
    mieter[f"F{row}"] = we["wohnflaeche_qm"]
    # G..K leer (kein State-Feld)
    miete = state["modul_5"]["we_mieten"][i]
    mieter[f"J{row}"] = round(miete["ist_miete_eur_pro_qm"] * we["wohnflaeche_qm"], 2)
    mieter[f"Y{row}"] = miete["mietspiegel_obergrenze_eur_pro_qm"]

# Mietspiegel-Mittelwert M6 (gewichtet)
m6 = sum(w["sollmiete_eur_pro_qm"] * we["wohnflaeche_qm"]
         for w, we in zip(state["modul_5"]["we_mieten"], state["modul_2"]["we_liste"])) \
     / sum(we["wohnflaeche_qm"] for we in state["modul_2"]["we_liste"])
mieter["M6"] = round(m6, 2)
mieter["P6"] = 0.15

# ===== 3. RENO (Mengen aus M3, Pauschal-Werte für Subvention/WEG) =====
reno = wb["RENO"]

# WEG-Teilung: Zeile 104
if state["modul_4"]["weg_teilung_netto_eur"] > 0:
    reno["I104"] = 1
    # Default K104=12000 nicht überschreiben, ausser User wich ab
    template_weg = 12000
    if abs(state["modul_4"]["weg_teilung_netto_eur"] - template_weg) > 100:
        reno["K104"] = state["modul_4"]["weg_teilung_netto_eur"]

# RND-Gutachten: RENO Zeile 105 (ersetzt seit 2026-06-15 die Miet-Subvention)
# 600 EUR netto/WE (Vorlage-Default K105), Menge = Anzahl WE
N_we = len(state["modul_2"]["we_liste"])
reno["F105"] = "RND"
reno["I105"] = N_we
reno["K105"] = 600

# Mietsubvention -> VERKAUFSMATRIX!Y27 (immer NEGATIV; Y28=SUM(Y6:Y27) zieht sie vom VK-Erlös ab)
# Total = summe_eur_pro_monat × Reach-Time (60-Mo-Default falls reach_time nicht im State)
reach_time_default_mo = 60
total_subv = state["modul_5"].get(
    "mietsubventionen_total_eur",
    state["modul_5"]["mietsubventionen_summe_eur_pro_monat"] * reach_time_default_mo,
)
vk = wb["VERKAUFSMATRIX"]
vk["Y27"] = -round(total_subv, 2)

# Massnahmen (Mengen-Mapper)
KATEGORIE_RENO_MAPPING = {
    "Dach":      [(25, "neu_decken", "dachflaeche")],   # Default: Dach neu decken
    "Fassade":   [(18, "wdvs", "fassadenflaeche")],     # WDVS
    "Fenster":   [(50, "komplett", "fenster_stk")],
    "Heizung":   [(78, "zentral", "anzahl_we")],
    "Elektrik":  [(69, "neu_pro_qm", "wohnflaeche_gesamt")],
    "Sanitaer":  [(93, "bad_komplett", "wohnflaeche_gesamt")],
    "Boeden":    [(37, "laminat", "wohnflaeche_gesamt")],
    "Grundriss": [(30, "wand_einziehen", "anzahl_we")],
}
# Schätzungs-Heuristik für Menge falls nicht explizit aus State ableitbar
wohnflaeche_gesamt = sum(we["wohnflaeche_qm"] for we in state["modul_2"]["we_liste"])
dachflaeche = wohnflaeche_gesamt * 0.6        # Heuristik
fassadenflaeche = wohnflaeche_gesamt * 0.8    # Heuristik
fenster_pro_we = 6                              # Heuristik
mengen_lookup = {
    "wohnflaeche_gesamt": wohnflaeche_gesamt,
    "dachflaeche": dachflaeche,
    "fassadenflaeche": fassadenflaeche,
    "fenster_stk": fenster_pro_we * len(state["modul_2"]["we_liste"]),
    "anzahl_we": len(state["modul_2"]["we_liste"]),
}

for m in state["modul_4"]["massnahmen_liste"]:
    kat = m["kategorie"]
    if kat == "Sonstiges":
        continue  # WEG/Subvention/RND-Gutachten separat behandelt
    if kat not in KATEGORIE_RENO_MAPPING:
        continue
    for zeile, _, mengen_key in KATEGORIE_RENO_MAPPING[kat]:
        # Wenn der Modul-3-Eintrag einen konkreten Netto-Wert hat, ggf. Default-K
        # überschreiben (Vorsicht: nur wenn User explizit Preis pro Einheit kennt)
        # Default-Verhalten: nur Menge eintragen, K (Preis pro Einheit) unverändert
        menge = mengen_lookup.get(mengen_key, 1)
        reno[f"I{zeile}"] = round(menge, 0)

# ===== 4. KALKU!I13-I17: Portalpreise €/m² aus modul_1.eur_per_qm =====
# Quellen-Mapping (siehe docs/excel_handoff.md + Memory modul-0-portal-konsens):
#   I13 = Homeday
#   I14 = Immometrica PLZ-ETW         (ersetzt IS24-Preisatlas)
#   I15 = CHECK24
#   I16 = Interhyp
#   I17 = Grundstuecksmarktbericht    (aus Notion-DB, ersetzt Wohnungsmarktbericht)
# Excel rechnet selbst den Durchschnitt der gefuellten Werte ueber alle 5.
# Fehlende Werte bleiben leer → User kann manuell nachtragen.
kalku = wb["KALKU"]
eur_per_qm = (state.get("modul_1") or {}).get("eur_per_qm") or {}
_kalku_qm_map = {
    "I13": "homeday",
    "I14": "immometrica",
    "I15": "check24",
    "I16": "interhyp",
    "I17": "grundstuecksmarktbericht",
}
for cell, key in _kalku_qm_map.items():
    val = eur_per_qm.get(key)
    if val is not None:
        kalku[cell] = float(val)

# ===== 5. Verkauf Cashflow: AfA + Gebäudeanteil + Bewirtschaftungs-Rücklage (Werte) =====
# Sheet heißt seit 2026-06-25 "Verkauf Cashflow" (vorher "VK_CF").
vkcf = wb["Verkauf Cashflow"]
vkcf["C9"]  = round(state["modul_3"]["afa_empfehlung_prozent"] / 100, 4)   # AfA-Satz (z.B. 2.5% -> 0.025)
vkcf["C10"] = round(state["modul_2"]["gebaeude_anteil_prozent"] / 100, 4)  # Gebäudeanteil am KP (z.B. 75 -> 0.75)
# Laufende Instandhaltungsrücklage EUR/m²/Jahr aus RND-Staffel (II.BV indexiert / Praxis 2025).
# Speist die C8-Formel im Template: C8 = (C66+C67)/C69 = (Verwaltung + Rücklage)/Nettokaltmiete.
# Nur nicht-umlagefähige Vermieterkosten — Versicherung + Grundsteuer sind umlagefähig (Mieter zahlt).
rnd = state["modul_3"]["rnd_jahre"]
ruecklage_eur_qm = 10 if rnd >= 40 else (14 if rnd >= 20 else 18)
vkcf["C64"] = ruecklage_eur_qm
# C62 (Verwaltung 35 EUR/WE/Mo), C7 (Grenzsteuer 0,42), C13 (Loan-Faktor) bleiben Template-Default

# ===== 6. Excel-Comments (Werte die nicht in dedizierte Zellen passen) =====
# AfA-Empfehlung als Comment auf KALKU!H10 (Headline VORKALKULATION)
afa_text = (
    f"Aufteiler-Skill Modul 2 RND/AfA:\n"
    f"AfA-Empfehlung: {state['modul_3']['afa_empfehlung_prozent']:.2f}% (Korridor "
    f"{state['modul_3']['afa_korridor_prozent']['min']:.2f}–{state['modul_3']['afa_korridor_prozent']['max']:.2f}%)\n"
    f"RND: {state['modul_3']['rnd_jahre']} Jahre (rnd_frozen=true)\n"
    f"Mod-Score: {state['modul_3']['mod_score']}/20\n"
    f"BFH IX R 7/23: Gutachten zwingend, dies ist eine Vorprüfung."
)
kalku["H10"].comment = Comment(afa_text, "Aufteiler-Skill")

# Bewertungs-Score als Comment auf BESICHTIGUNG!A40
verdict_text = (
    f"Aufteiler-Skill Modul 5 Deal-Bewertung:\n"
    f"Score: {state['modul_6']['bewertungs_score']}/100 (Platzhalter-Logik)\n"
    f"Status: {state['modul_6']['status'].upper()}\n"
    f"PDF: {state['modul_6']['pdf_pfad']}"
)
besichtigung["A40"].comment = Comment(verdict_text, "Aufteiler-Skill")

# Mietsubvention-Verweis als Comment auf VERKAUFSMATRIX!Y27 (Subventionskosten, negativ)
subv_text = (
    f"Aufteiler-Skill Modul 5 Mietsubvention (Subventionskosten, negativ):\n"
    f"Σ €/Monat (Durchschnitt über Reach-Time): "
    f"{state['modul_5']['mietsubventionen_summe_eur_pro_monat']:.2f} EUR/Mo\n"
    f"Gesamt-Pauschal (60-Mo-Default): {total_subv:.2f} EUR\n"
    f"Stufen-Details siehe runs/<slug>/modul-4-output.md."
)
vk["Y27"].comment = Comment(subv_text, "Aufteiler-Skill")

wb.save(dst)
```

**3d) Plausibilitäts-Prüfung:**

- PDF-Datei existiert auf Platte nach Build.
- Excel-Datei existiert nach Save.
- `bewertungs_score` zwischen 0 und 100.
- Alle Pflicht-Zellen in Excel ≠ leer (Stichprobe: `MIETER!A8`, `KALKU!C20`, `KALKU!C26`).

## 4. Output erzeugen (Drei Zonen)

**Zone A — Daten-Block:**

```
| Position                | Wert                                              |
|-------------------------|---------------------------------------------------|
| Bewertungs-Score        | <0-100> / 100 (Platzhalter, siehe Hinweis)        |
| Verdict-Kategorie       | GO / GRENZWERTIG / STOP                           |
| PDF-Pfad                | Aufteiler_<Strassenkurz>_<YYYY-MM-DD>.pdf         |
| Excel-Pfad              | Kalkulation_<Strassenkurz>.xlsx                   |
| Module mit Status rot   | <Liste oder "—">                                  |
| Module mit Status gelb  | <Liste oder "—">                                  |
```

```
| Score-Aggregation       | Status | Konfidenz | Delta |
|-------------------------|--------|-----------|-------|
| Modul 0 Quick-Check     | <s>    | <k>       | <Δ>   |
| Modul 1 Objektbasis     | <s>    | <k>       | <Δ>   |
| Modul 2 RND/AfA         | <s>    | <k>       | <Δ>   |
| Modul 3 Massnahmen      | <s>    | <k>       | <Δ>   |
| Modul 4 Miete           | <s>    | <k>       | <Δ>   |
| Basis 70 + Summe Deltas | -      | -         | <Σ>   |
| Score (clamped 0-100)   |        |           | <X>   |
```

**Zone B:**
```
Tiefenstufe: 1 von 1 (Platzhalter-Score; echte Methodik folgt)
Konfidenz: niedrig (Platzhalter)
```

**Zone C — Begründung:**

1. **Wichtigste Annahmen** (max 5 Bullets) — z.B. „Score-Logik: Basis 70, je rot −10, je gelb −5, je Konfidenz −2/−5", „Bewirtschaftungs-Quote Default 20 %".
2. **Risiken / Unsicherheiten** (max 5 Bullets) — z.B. „Score-Methodik noch offen (Platzhalter)", „Brutto/Netto-Excel-Verifikation TODO".
3. **Empfehlung** (1–3 Sätze) — z.B. „PDF + Excel als Prüfungs-Dokumente vor Notartermin. Score ist Platzhalter — echte Methodik folgt."

**Pflicht-Hinweis (immer in Zone C anhängen):**

```
HINWEIS: bewertungs_score ist Platzhalter (Ampel-Aggregation Modul 0-4).
Echte Score-Methodik folgt aus parallelem Optimierungs-Prozess.
Siehe plans/2026-05-12-score-logik-modul-5-offen.md.
```

## 5. State persistieren

1. `modul_6`-Block bauen:
   ```json
   {
     "status": "<gruen|gelb|rot>",
     "bewertungs_score": <number 0-100>,
     "pdf_pfad": "Aufteiler_<Strassenkurz>_<YYYY-MM-DD>.pdf",
     "excel_pfad": "Kalkulation_<Strassenkurz>.xlsx"
   }
   ```
   Status-Ableitung aus Score:
   - `score >= 70` → `status = "gruen"` (GO)
   - `50 <= score < 70` → `status = "gelb"` (GRENZWERTIG)
   - `score < 50` → `status = "rot"` (STOP)
2. `objekt.letzter_modul_lauf` auf `"modul_6"` setzen.
3. State schreiben.
4. `runs/<slug>/modul-5-output.md` mit Zonen A/B/C schreiben.
5. Validator-Lauf: `python tools/validate_state.py runs/<slug>/state.json`. Exit 0 = OK.

## 6. Self-Check (Pflicht vor Übergabe)

- [ ] Alle Pflichtfelder befüllt (status, bewertungs_score, pdf_pfad, excel_pfad)
- [ ] PDF-Datei existiert auf Platte (`runs/<slug>/Aufteiler_*.pdf` ist eine echte Datei mit > 0 Bytes)
- [ ] Excel-Datei existiert auf Platte (`runs/<slug>/Kalkulation_*.xlsx` ist eine echte Datei mit > 0 Bytes)
- [ ] `bewertungs_score` zwischen 0 und 100
- [ ] Alle Module 0–4 unverändert im State (kein Modul-5-Schreiben in Modul-0-4-Blöcke)
- [ ] `modul_3.rnd_frozen` unverändert auf `true`
- [ ] Platzhalter-Hinweis in `modul-5-output.md` Zone C enthalten
- [ ] PDF-Skill-Regeln R1–R13 angewendet (Self-Check aus `aufteiler-pdf-export` Sektion 5)
- [ ] Excel: alle Pflicht-Zellen aus `docs/excel_handoff.md` befüllt
- [ ] **Werte-Vorschau (Zelle | Wert | Quell-Modul) im Chat gezeigt, BEVOR die Excel-Freigabe-Frage gestellt wurde** — keine Zelle geschrieben, die nicht in der Vorschau stand
- [ ] Excel-Freigabe via AskUserQuestion eingeholt (nicht automatisch befüllt) — **Pauschal-Freigaben aus früheren Nachrichten NICHT als Bestätigung gewertet**
- [ ] Bei User-Korrekturen: Quell-Feld in `state.json` gepatcht (nicht nur Excel), Validator exit 0, Vorschau aktualisiert + erneut gefragt
- [ ] PDF-Freigabe via AskUserQuestion eingeholt (nicht automatisch generiert)
- [ ] Validator-CLI exit 0

Bei rot → kein state.json-Schreiben, an Orchestrator zurück.

## 7. Chat-Visualisierung + Übergabe an Orchestrator (Pflicht-Reihenfolge)

**Schritt 1 — Pflicht-Visualisierung im Chat (NIE überspringen):** Den kompletten Zonen-Output 1:1 im Chat rendern — identisch zu dem, was in die Audit-Datei geschrieben wurde: Zone A (Eckdaten + Score-Aggregation als Markdown-Tabellen), Zone B, Zone C inkl. Platzhalter-Hinweis. (Die Excel-Werte-Vorschau aus 3b wurde bereits VOR der Excel-Freigabe gezeigt.) Grundsatz: **Alles, was in PDF oder Excel gelandet ist, hat der User vorher im Chat gesehen.** Ein Einzeiler ist NIE ausreichend.

**Schritt 2 — Status-Zeile (NACH der Visualisierung):**
```
Modul 6 grün. Score <X>/100 (Platzhalter). PDF: runs/<slug>/Aufteiler_<…>.pdf, Excel: runs/<slug>/Kalkulation_<…>.xlsx. Audit in runs/<slug>/modul-5-output.md.
```

Plus Pflicht-Hinweise:
- „PDF + Excel sind Prüfungs-Dokumente, kein Gutachten."
- „Score ist Platzhalter — echte Methodik folgt."

============================================================

## Änderungen

- **2026-09-11 — Template V2 „Verkauf Cashflow" als Vorwärtskalkulation je Wohnung:** Das Werkzeug erkennt migrierte Templates am Defined Name `AUFTEILER_TPL_V2` und schreibt dann zusätzlich den Datenblock je WE (Regler €/m² = `modul_1.eur_per_qm.median`, MEA-Zähler, Leerstand, Garagen/Stellplätze mit Mieten, Ziel-Sollmiete = (Sollmiete + Obergrenze)/2 × Fläche, Modul-5-Subvention, Reach-Time, Hausgeld-Paar/Quote) und `N6`/`N7`/`N8` (Grundstück mit Quellen-Kommentar, BRW, MEA-Nenner). In V2 ist `MIETER!K` ein Formel-Spiegel und wird nicht geschrieben. Vertrag: `docs/excel_handoff_vkcf.md` (generiert), Spec `docs/superpowers/specs/2026-09-11-vkcf-vorwaertskalkulation-design.md`. Abnahme: `tools/verify_vkcf_vorwaertskalkulation.py` + `tools/verify_vkcf_excel_com.ps1`.
- **2026-09-11 — Excel-Befüllung als Werkzeug** (`tools/export_excel.py`): Der Excel-Write-Block aus Sektion 3b läuft jetzt reproduzierbar (`--dry-run` = Werte-Vorschau, `--out`, `--force` mit Backup, Temp-Datei + `os.replace`). Neue Writes aus den Modul-5-Feldern der Verkaufs-Kalkulation: `MIETER!G` (Mietername aus `objektdaten.json`), `H`/`I` (Einzug, letzte Erhöhung — als `datetime.date`), `J` aus dem Sollstellungs-Betrag `ist_miete_eur_pro_monat` (vorher `€/m² × Fläche`, verlor Cents), `K` = Garagen- + Stellplatzmiete (Mietspalte, keine Stückzahl), `T4` § 559, `P6`/`B34` aus `kappungsgrenze`. Roundtrip gegen einen echten Skill-Export (Rautenstrauchstraße 1): RENO, Verkauf Cashflow, VERKAUFSMATRIX, Checkliste, NK identisch. Offen im Werkzeug: `BESICHTIGUNG!B18–B23/B28` und `KALKU!E35–E38` (Zustandstexte, Heizung, Schmerzgrenze) — die schreibt der Skill-Lauf weiterhin aus Modul-3/4-Texten. Werte-Vorschau-Tabelle nachgezogen.

- **2026-06-26 — Bewirtschaftung komponentenbasiert + Rücklagen-Topf** (`plans/2026-06-26-modul6-bewirtschaftung-ruecklage.md`): Excel-Write-Block (Sektion 3b, „===== 5. Verkauf Cashflow") um `C64` erweitert = laufende Instandhaltungsrücklage €/m²/Jahr aus RND-Staffel (RND≥40→10, 20–40→14, <20→18; II.BV indexiert/Praxis 2025). C64 speist die neue C8-Formel im Template (`=IFERROR((C66+C67)/C69,0.2)` = (Verwaltung + Rücklage)/Nettokaltmiete, nur nicht-umlagefähige Vermieterkosten — Versicherung + Grundsteuer sind umlagefähig und bleiben draußen). Template-Sektionen (via `tools/migrate_vkcf_bewirtschaftung.py`): Sektion 1 (Bewirtschaftungs-Komponenten Z.61–70, Rücklage in 3 Größen €/m²·J / €/J / €-10-J) + Sektion 2 (Rücklagen-Topf-Sensitivität Z.73–87, WEG-Topf 0–50k → Quote & max. VK-Preis). Werte-Vorschau um C64-Zeile, Sektion 1a/2 (Quote→Rücklage), PDF-Sektion 8.5 neu beschrieben. Kein Schema-Eingriff (Rücklage on-the-fly aus `modul_3.rnd_jahre`).

- **2026-06-25 — Verkauf-Cashflow-Umbau** (`plans/2026-06-25-excel-vkcf-ist-miete-schutz.md`): Reiter „VK_CF" → „Verkauf Cashflow" umbenannt (Template + 20 VERKAUFSMATRIX-Referenzen). Neuer Excel-Write-Block (Sektion 3b Code, „===== 5. Verkauf Cashflow"): `C9` = `modul_3.afa_empfehlung_prozent/100` (AfA-Satz), `C10` = `modul_2.gebaeude_anteil_prozent/100` (Gebäudeanteil) — als **Werte** statt nur Comment, damit die VK-Rückrechnung mit den ermittelten Werten rechnet. Werte-Vorschau-Tabelle um beide Zellen erweitert. `C7` (Grenzsteuer, Template-Default jetzt 0,42) und `C13` (Loan-Faktor) werden nicht geschrieben. Kein Schema-Eingriff (AfA + Gebäudeanteil sind Bestandsfelder).

- **2026-06-11 — Excel-Schutz verschärft + Pflicht-Visualisierung** nach Datteln-Lauf (`plans/2026-06-11-orchestrator-gate-haertung-visualisierung.md`): Sektion 3b um Pflicht-Werte-Vorschau (Zelle | Wert | Quell-Modul, alle Zellen inkl. Comments) VOR der Excel-Frage + Korrektur-Schleife (State-Patch + Validator → Vorschau neu → erneut fragen) erweitert; Anti-Pauschal-Freigabe-Regel in Sektion 2, 3b und 3c (frühere „analysiere alles durch"-Aussagen sind KEINE Excel-/PDF-Bestätigung); neue Sektion 1a Entscheidungs-Weichen (Bewirtschaftungs-Quote etc.); Sektion 7 von „Eine Zeile" auf Visualisierung → Status-Zeile umgestellt; Self-Check um Vorschau-/Anti-Pauschal-Checks erweitert; Status-Zeile auf echte Modul-Nummer (6) korrigiert. Audit-Dateiname `modul-5-output.md` bewusst unverändert (Bestands-Vertrag).
