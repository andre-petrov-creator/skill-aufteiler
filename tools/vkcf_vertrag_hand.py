"""Handgepflegter Teil des Spaltenvertrags "Verkauf Cashflow" (Vorwaertskalkulation je Wohnung).

Quelle: Revision final r2 (scratchpad/revision_final_r2.json, Abschnitte mitzieher/formatierung) - die
Freitext-Eintraege dort sind hier in Dataclasses uebersetzt. Formeln mit Platzhaltern (siehe vkcf_vertrag):
{key} Spalte der Zeile, {key$@sum} Summenzelle absolut, {p:key} Parameter, {MIETER!F} Fremdblatt mit Offset.
Wird von vkcf_vertrag_daten.py (generiert) importiert.
"""
import vkcf_vertrag as V  # zur Importzeit teilweise initialisiert - Dataclasses und Konstanten sind bereits definiert

LAY = V.LAYOUT
ROWS = range(LAY.first, LAY.last + 1)                              # VKCF-Datenzeilen
VM_ROWS = range(LAY.verkaufsmatrix_row_of_first, LAY.verkaufsmatrix_row_of_first + 20)   # VERKAUFSMATRIX 6..25
MI_ROWS = range(LAY.mieter_row_of_first, LAY.mieter_row_of_first + 20)                    # MIETER 8..27
VM_TO_MI = LAY.mieter_row_of_first - LAY.verkaufsmatrix_row_of_first                      # VERKAUFSMATRIX-Zeile -> MIETER-Zeile

# ---------------------------------------------------------------- Mitzieher (Formeln ausserhalb des Datenblocks)
MITZIEHER: list = []

for r in ROWS:
    vm = r + LAY.offsets["VERKAUFSMATRIX"]
    mi = r + LAY.offsets["MIETER"]
    MITZIEHER += [
        V.Mitzieher("VERKAUFSMATRIX", f"Y{vm}", 'IF(ISNUMBER({abgabepreis}),{abgabepreis},"")', r,
                    "MEIN VERKAUFSPREIS = gesetzter Abgabepreis gesamt (Wohnung inkl. Aufschlag + Garage + Stellplatz)"),
        # Zahl (0 ohne Garage), nie "" - die Bestandsformel W = U+V rechnet sonst #WERT! (Excel-COM-Befund 2026-09-11)
        V.Mitzieher("VERKAUFSMATRIX", f"V{vm}", 'IF(NOT(ISNUMBER({MIETER!F})),"",N({garage_preis})+N({stellplatz_preis}))', r,
                    "Spiegel aus Verkauf Cashflow Q+R (vorher Handeingabe); 0 ohne Garage/Stellplatz"),
        V.Mitzieher("VERKAUFSMATRIX", f"X{vm}", 'IF(ISNUMBER({individueller_aufschlag}),{individueller_aufschlag},"")', r,
                    "Spiegel aus Verkauf Cashflow O (vorher Handeingabe)"),
        V.Mitzieher("VERKAUFSMATRIX", f"AA{vm}", 'IF(ISNUMBER({bruttomietrendite}),{bruttomietrendite},"")', r,
                    "Rendite auf MEIN PREIS = Bruttomietrendite aus Verkauf Cashflow"),
        V.Mitzieher("MIETER", f"K{mi}", 'IF(AND(NOT(ISNUMBER({garage_miete})),NOT(ISNUMBER({stellplatz_miete}))),"",N({garage_miete})+N({stellplatz_miete}))', r,
                    "Garagen-/Stellplatzmiete als Formel-Spiegel aus Verkauf Cashflow AL+AM; K28/K30/J31 (JNKM) bleiben"),
    ]

# VERKAUFSMATRIX Bestandsformeln N/P/R/T (Zeilen 6-25): gegen leere Zeile und fehlende Angaben gesichert -
# vorher war W "Vorschlag Verkaufspreis" in jedem Export #WERT! (COM-Befund 2026-09-11, V1-Alt-Export identisch)
for vm in VM_ROWS:
    mi = vm + VM_TO_MI
    MITZIEHER += [
        V.Mitzieher("VERKAUFSMATRIX", f"N{vm}", f'IF(NOT(ISNUMBER(H{vm})),"",IF(M{vm}="Kein Balkon",H{vm}*(-0.05),H{vm}*0))', None,
                    "Balkon-Abschlag ausgerollt (Bestand nur Z.22-25) und gegen leere Zeile gesichert"),
        V.Mitzieher("VERKAUFSMATRIX", f"P{vm}", f'IF(NOT(ISNUMBER(H{vm})),"",IF(ISBLANK(O{vm}),0,H{vm}*MIN((YEAR(TODAY())-O{vm})*0.003,0.09)*-1))', None,
                    "Etagenheizungs-Abschlag ausgerollt; 0 ohne Baujahr"),
        V.Mitzieher("VERKAUFSMATRIX", f"R{vm}",
                    f'IF(ISNUMBER(MIETER!F{mi}),IF(Q{vm}="renoviert",H{vm}*0.05,IF(Q{vm}="teilweise renoviert",H{vm}*0,IF(Q{vm}="unrenoviert",H{vm}*-0.05,0))),"")',
                    None, "Renovierungs-Abschlag: 0 statt \"\" ohne Zustandsangabe"),
        V.Mitzieher("VERKAUFSMATRIX", f"T{vm}",
                    f'IF(ISNUMBER(MIETER!F{mi}),IF(OR(S{vm}="EG",S{vm}="1.OG",S{vm}="2.OG",S{vm}="OG",S{vm}="über 2.OG mit Aufzug"),H{vm}*0,IF(OR(S{vm}="UG",S{vm}="über 2.OG ohne Aufzug"),H{vm}*(-0.05),0)),"")',
                    None, "Etagen-Abschlag: 0 statt \"\" bei unbekannter Schreibweise (Modul 6 schreibt EG/1.OG/3.OG)"),
    ]

# Alt-Kontrollsektionen ab Zeile 41 (bleiben an Ort und Stelle; Bezuege auf Parameter/Summen ueber Schluessel)
MITZIEHER += [
    V.Mitzieher(V.SHEET, "C44", "{abgabe_wohnung@sum}", None, "VK Wohnungen Vorwaerts-Ansatz = Summe Abgabepreis Wohnungen (vorher Rueckrechnung)"),
    V.Mitzieher(V.SHEET, "C70", "{p:bewirt_quote_alt}", None, "Quote-Spiegel (Bestand =C8)"),
    V.Mitzieher(V.SHEET, "D56", 'IFERROR(({p:k_faktor_alt}/C56)*{max_tragbar_fin$@sum}+{p:kp_assets_gesamt},"")', None, "Sensitivitaet auf Summe max. tragbar (109,3 %)"),
    V.Mitzieher(V.SHEET, "D57", 'IFERROR({max_tragbar_fin$@sum}+{p:kp_assets_gesamt},"")', None, "Basis-Szenario"),
    V.Mitzieher(V.SHEET, "D58", 'IFERROR(({p:k_faktor_alt}/C58)*{max_tragbar_fin$@sum}+{p:kp_assets_gesamt},"")', None, ""),
    V.Mitzieher(V.SHEET, "D59", 'IFERROR(({p:k_faktor_alt}/C59)*{max_tragbar_fin$@sum}+{p:kp_assets_gesamt},"")', None, ""),
]
for r, shift in ((56, "-0.005"), (57, "0"), (58, "0.005"), (59, "0.01")):
    MITZIEHER.append(V.Mitzieher(V.SHEET, f"B{r}", f"{{p:zins}}+{shift}", None, "Zins-Szenario (Bestand =$C$5+x)"))
    MITZIEHER.append(V.Mitzieher(V.SHEET, f"C{r}",
                                 f"{{p:loan_faktor_vorwaerts}}*((B{r}+{{p:tilgung}})-{{p:steuersatz}}*B{r}-{{p:steuersatz}}*{{p:gebaeude_anteil_std}}*{{p:afa_satz_std}}*(1+{{p:knk}}))/12",
                                 None, "k-Faktor der Sensitivitaet: Loan-Faktor der Vorwaertsrechnung, AfA-Term mit (1+KNK) - identisch zu k global"))
for r in range(77, 88):
    MITZIEHER += [
        V.Mitzieher(V.SHEET, f"D{r}", f'IF(OR(NOT(ISNUMBER({{p:nkm_jahr}})),{{p:nkm_jahr}}=0),"",($C$66+C{r})/{{p:nkm_jahr}})', None,
                    "Ruecklagen-Topf: Quote gegen leere/0-Nettokaltmiete gesichert"),
        V.Mitzieher(V.SHEET, f"E{r}", f"(((1-{{p:steuersatz}})*(1-D{r})*{{kaltmiete$@sum}})-{{p:anzahl_we}}*{{p:ziel_cf}})/{{p:k_faktor_alt}}", None,
                    "Ruecklagen-Topf: Nettokaltmiete aus der Summenzeile"),
    ]

# ---------------------------------------------------------------- Labels der Bestandssektionen + Fremdblaetter
LABELS: list = [
    V.Label(V.SHEET, "A41", "VERGLEICH: MARKT-ANSATZ vs. VORWAERTS-ANSATZ"),
    V.Label(V.SHEET, "A44", "VK Wohnungen VORWAERTS-ANSATZ (Abgabepreis inkl. Aufschlag, ohne Garage/Provision)"),
    V.Label(V.SHEET, "A53", "SENSITIVITAET: SUMME MAX. TRAGBAR (109,3 %) BEI ZINS-SHIFT (Alt-Kontrolle, globale Annahmen)"),
    V.Label(V.SHEET, "A61", "BEWIRTSCHAFTUNG (nicht umlagefaehig) - Standard fuer Wohnungen ohne Hausgeld-Angabe; speist die Alt-Kontrolle"),
    V.Label(V.SHEET, "A73", "RUECKLAGEN-TOPF -> Quote & max. Verkaufspreis (Alt-Kontrolle, globale Annahmen)"),
    V.Label("VERKAUFSMATRIX", "V5", "PREIS GARAGE /\nSTELLPLATZ", "Spiegel aus Verkauf Cashflow Q+R - dort eintragen"),
    V.Label("VERKAUFSMATRIX", "X5", "INDIVIDUELLER\nAUF-/ABSCHLAG", "Eingabe im Reiter Verkauf Cashflow, Spalte O"),
    V.Label("VERKAUFSMATRIX", "Y5", "MEIN\nVERKAUFSPREIS", "= gesetzter Abgabepreis gesamt aus Verkauf Cashflow (Spalte S)"),
    V.Label("MIETER", "K7", "Garagen-/Stellpl.-\nmiete", "Formel-Spiegel aus Verkauf Cashflow AL+AM - dort eintragen"),
]

# Legende rechts neben den Parametern (eine Zeile je Eintrag)
LEGENDE: list = [
    "Hellgelb = Eingabe je Wohnung; leer = Standard aus dem Käuferprofil greift",
    "Ampel: Grün = Preis trägt, Gelb = knapp (Toleranz), Rot = über max. tragbar oder Datenfehler, Grau = Angabe fehlt",
    "Mint = Standard-Rückfall aktiv (Feld leer); Orange = Ist-Miete manuell angehoben / Eigenkapital trotz Vollfinanzierung",
    "Rücklage mindert nur den Cashflow, nicht die Steuer (BFH IX R 19/24); Hausgeld ohne Wirtschaftsplan = Verwaltung + Rücklage-Standard",
    "Kontrollspalten: max. tragbar = (Ertrag nach Steuer ohne Finanzierung − Ziel-CF + Garage/Stellplatz netto) / k",
    "k = Loan-Faktor × [(Zins + Tilgung) − s × Zins − s × (1 + KNK) × AfA × Grenz-Gebäudeanteil] / 12",
    "Hilfsspalten sind per Gruppierung eingeklappt — Schaltfläche + über der Tabelle",
]

# ---------------------------------------------------------------- Gruppierung (Outline, eingeklappt)
GRUPPEN: list = [
    ("mea_anteil", "mea_anteil"), ("abgabepreis_qm", "beurkundet"), ("miete_eur_qm", "miete_eur_qm"), ("soll_vorschlag", "soll_vorschlag"),
    ("bewirt_quote", "bewirt_1pp_preis_eur"), ("gebaeude_anteil_brw", "gebaeude_anteil_brw"), ("gebaeude_anteil_quelle", "gebaeude_anteil_quelle"),
    ("afa_satz_eff", "afa_satz_eff"), ("ruecklage_nachholbar", "ruecklage_nachholbar"), ("nettoertrag_vor_fin", "k_faktor_fin"),
]

# ---------------------------------------------------------------- Bedingte Formatierung (helle Toene, je Regel start_color = end_color)
CF_REGELN: list = []
for key in ("provision_pct", "bewirtschaftungsquote_schaetzung", "hausgeld_nicht_umlagefaehig", "hausgeld_ruecklage", "gebaeude_anteil", "afa_satz"):
    CF_REGELN.append(V.CfRegel((key,), f'AND({{wohnflaeche_m2$}}<>"",{{{key}}}="")', V.CF_MINT, "Eingabe mit Standard-Rueckfall: mint solange leer"))
CF_REGELN += [
    V.CfRegel(("abgabe_eur_qm_regler",), 'AND({wohnflaeche_m2$}<>"",{abgabe_eur_qm_regler}="")', V.CF_GELB, "Pflicht-Eingabe ohne Standard: gelb solange leer"),
    V.CfRegel(("kaltmiete_override",), '{kaltmiete_override}<>""', V.CF_ORANGE, "Override sichtbar"),
    V.CfRegel(("kaltmiete",), 'AND(ISNUMBER({kaltmiete_override}),{kaltmiete_override}>{MIETER!J})', V.CF_ORANGE, "Ist-Miete manuell angehoben"),
    V.CfRegel(("bewirtschaftungsquote_schaetzung",), 'AND({wohnflaeche_m2$}<>"",{bewirtschaftungsquote_schaetzung}<>"",{hausgeld_nicht_umlagefaehig}<>"")', V.CF_WARNROT, "zwei Hausgeld-Quellen"),
    V.CfRegel(("gebaeude_anteil_effektiv",), 'AND(ISNUMBER({gebaeude_anteil_effektiv}),{gebaeude_anteil_effektiv}<=0)', V.CF_WARNROT, "Bodenwert >= Kaufpreis"),
    V.CfRegel(("delta_regler_zu_max",), 'AND(ISNUMBER({delta_regler_zu_max}),{delta_regler_zu_max}>0)', V.CF_WARNROT, "Regler ueber max. tragbar"),
    V.CfRegel(("eigenkapital",), 'AND(ISNUMBER({eigenkapital}),{eigenkapital}>0,{p:finanzierungsfall}=2)', V.CF_ORANGE, "Eigenkapital trotz 'alles finanziert'"),
]
AMPEL = {"GRUE": V.AMPEL_GRUEN, "GELB": V.AMPEL_GELB, "ROT:": V.AMPEL_ROT, "GRAU": V.AMPEL_GRAU}
for key in ("ampel_100", "ampel_fin"):
    for pref, farbe in AMPEL.items():
        CF_REGELN.append(V.CfRegel((key,), f'LEFT({{{key}}},4)="{pref}"', farbe, f"Ampel {pref.strip(':')}"))

# ---------------------------------------------------------------- Datenpruefung (allow_blank ueberall: leer = Standard)
DV_REGELN: list = [
    V.DvRegel(("leerstand",), "list", formula1='"ja,nein"'),
    V.DvRegel(("abgabe_eur_qm_regler",), "decimal", "between", "0", "20000"),
    V.DvRegel(("individueller_aufschlag",), "decimal", "between", "-100000", "100000"),
    V.DvRegel(("provision_pct",), "decimal", "between", "0", "0.15", param_keys=("provision_std",)),
    V.DvRegel(("gebaeude_anteil",), "decimal", "between", "0.5", "1"),
    V.DvRegel(("afa_satz",), "decimal", "between", "0.01", "0.06"),
    V.DvRegel(("garage_preis", "stellplatz_preis", "kaltmiete_override", "soll_miete", "mietsubvention_eur_pro_monat", "garage_miete", "stellplatz_miete",
               "hausgeld_nicht_umlagefaehig", "hausgeld_ruecklage"), "decimal", "greaterThanOrEqual", "0"),
    V.DvRegel(("bewirtschaftungsquote_schaetzung",), "decimal", "between", "0", "0.6"),
    V.DvRegel(("garagen_anzahl", "stellplaetze_anzahl", "mea_zaehler", "reach_time_monate"), "whole", "greaterThanOrEqual", "0"),
    V.DvRegel((), "decimal", "between", "0", "0.2", param_keys=("knk",)),
    V.DvRegel((), "decimal", "greaterThan", "0", param_keys=("grundstueck_qm", "brw")),
    V.DvRegel((), "whole", "greaterThan", "0", param_keys=("mea_nenner",)),
    V.DvRegel((), "decimal", "between", "0", "0.05", param_keys=("afa_garage", "afa_stellplatz")),
    V.DvRegel((), "decimal", "between", "0", "0.5", param_keys=("ampel_toleranz",)),
    V.DvRegel((), "whole", "between", "1", "120", param_keys=("sperrfrist_monate",)),
]

# ---------------------------------------------------------------- Layout-Zusaetze
DATUMSZELLEN: list = [("MIETER", f"{c}{r}") for c in ("H", "I") for r in MI_ROWS]   # Zahlenformat dd.mm.yyyy (idempotent)

# ---------------------------------------------------------------- Roundtrip: was ausserhalb des Reiters geaendert sein darf
ERLAUBTE_AENDERUNGEN: set = set()
for m in MITZIEHER:
    if m.sheet != V.SHEET:
        ERLAUBTE_AENDERUNGEN.add((m.sheet, m.zelle))
for lb in LABELS:
    if lb.sheet != V.SHEET:
        ERLAUBTE_AENDERUNGEN.add((lb.sheet, lb.zelle))
