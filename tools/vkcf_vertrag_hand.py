"""Handgepflegter Teil des Spaltenvertrags "Verkauf Cashflow" (Vorwaertskalkulation je Wohnung).

Urspruenglich aus Revision final r2 (Abschnitte mitzieher/formatierung) uebersetzt; seit Layout 3
(2026-10-25, Eingabe-Wege) direkt hier gepflegt. Formeln mit Platzhaltern (siehe vkcf_vertrag):
{key} Spalte der Zeile, {key$@sum} Summenzelle absolut, {p:key} Parameter, {MIETER!F} Fremdblatt mit Offset.
Wird von vkcf_vertrag_daten.py importiert.
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
        V.Mitzieher("VERKAUFSMATRIX", f"X{vm}", 'IF(AND(ISNUMBER({individueller_aufschlag}),LEFT({preis_quelle},6)="Regler"),{individueller_aufschlag},"")', r,
                    "Spiegel aus Verkauf Cashflow (Auf-/Abschlag); nur wenn der Regler den Preis setzt - im Rendite-/Cashflow-Weg wirkt er nicht"),
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

# Alt-Kontrollsektionen ab Zeile 41 (bleiben an Ort und Stelle; Bezuege auf Parameter/Summen ueber Schluessel).
# Layout 3: Zins-Sensitivitaet A53:E59 und Text-Ampel C50 entfallen (V.ENTFERNTE_BEREICHE).
MITZIEHER += [
    V.Mitzieher(V.SHEET, "C44", "{abgabe_wohnung@sum}", None, "VK Wohnungen Vorwaerts-Ansatz = Summe Abgabepreis Wohnungen (vorher Rueckrechnung)"),
    V.Mitzieher(V.SHEET, "C70", "{p:bewirt_quote_alt}", None, "Quote-Spiegel (Bestand =C8)"),
]
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
    V.Label(V.SHEET, "A61", "BEWIRTSCHAFTUNG (nicht umlagefaehig) - Standard fuer Wohnungen ohne Hausgeld-Angabe; speist die Alt-Kontrolle"),
    V.Label(V.SHEET, "A73", "RUECKLAGEN-TOPF -> Quote & max. Verkaufspreis (Alt-Kontrolle, globale Annahmen)"),
    V.Label("VERKAUFSMATRIX", "V5", "PREIS GARAGE /\nSTELLPLATZ", "Spiegel aus Verkauf Cashflow Q+R - dort eintragen"),
    V.Label("VERKAUFSMATRIX", "X5", "INDIVIDUELLER\nAUF-/ABSCHLAG", "Eingabe im Reiter Verkauf Cashflow (Auf-/Abschlag); wirkt nur im Regler-Weg"),
    V.Label("VERKAUFSMATRIX", "Y5", "MEIN\nVERKAUFSPREIS", "= Abgabepreis gesamt aus Verkauf Cashflow - je nach Eingabe-Weg aus Regler, Ziel-Rendite oder Ziel-Cashflow"),
    V.Label("MIETER", "K7", "Garagen-/Stellpl.-\nmiete", "Formel-Spiegel aus Verkauf Cashflow (Miete Garage + Stellplatz) - dort eintragen"),
]

# Legende links unten unter dem Kaeuferprofil (Farbfeld + Stichwort | Erklaerung)
LEGENDE: list = [
    V.LegendenEintrag("Eingabe", V.FARBE_EINGABE, "beschreibbares Feld - je Wohnung in der Tabelle oder oben im Parameterblock"),
    V.LegendenEintrag("Annahme", V.FARBE_EINGABE, "Eingabefeld je Wohnung leer = Standardwert aus dem Parameterblock greift (Provision, Hausgeld, AfA, Gebäudeanteil ...)"),
    V.LegendenEintrag("Ergebnis", None, "Formel - nicht überschreiben; Hilfsspalten über die Schaltfläche + über der Tabelle aufklappen"),
    V.LegendenEintrag("Aktiv", V.FARBE_AKTIV, "bestimmt gerade den Preis (Eingabe-Weg rechts); grau = wirkt im gewählten Weg nicht"),
    V.LegendenEintrag("Hinweis", V.CF_ORANGE, "orange = Rückfall auf den Regler (keine Miete/kein Ziel) oder Miete angehoben; rot = Datenfehler"),
]

# ---------------------------------------------------------------- Gruppierung (Outline, eingeklappt)
GRUPPEN: list = [
    ("mea_anteil", "mea_anteil"), ("abgabepreis_qm", "beurkundet"), ("miete_eur_qm", "miete_eur_qm"), ("soll_vorschlag", "soll_vorschlag"),
    ("bewirt_quote", "bewirt_1pp_preis_eur"), ("gebaeude_anteil_brw", "gebaeude_anteil_brw"), ("gebaeude_anteil_quelle", "gebaeude_anteil_quelle"),
    ("afa_satz_eff", "afa_satz_eff"), ("ruecklage_nachholbar", "ruecklage_nachholbar"), ("nettoertrag_vor_fin", "kaufpreis_ziel"),
]

# ---------------------------------------------------------------- Bedingte Formatierung (helle Toene, je Regel start_color = end_color)
# Eingabe-Weg: 1 (oder leer) = Regler, 2 = Bruttomietrendite, 3 = Cashflow nach Steuern
WEG_REGLER = 'AND(N({p:eingabe_modus})<>2,N({p:eingabe_modus})<>3)'
WEG_RENDITE = 'N({p:eingabe_modus})=2'
WEG_CF = 'N({p:eingabe_modus})=3'
CF_REGELN: list = [
    V.CfRegel(("abgabe_eur_qm_regler",), f'AND({{wohnflaeche_m2$}}<>"",{WEG_REGLER})', V.FARBE_AKTIV, "Regler bestimmt den Preis", fett=True),
    V.CfRegel(("abgabe_eur_qm_regler", "individueller_aufschlag"), f'AND({{wohnflaeche_m2$}}<>"",NOT({WEG_REGLER}))', V.FARBE_INAKTIV, "wirkt im Rendite-/Cashflow-Weg nicht", schrift=V.SCHRIFT_INAKTIV),
    V.CfRegel(("ziel_rendite_override",), f'AND({{wohnflaeche_m2$}}<>"",{WEG_RENDITE})', V.FARBE_AKTIV, "Ziel-Rendite je WE bestimmt den Preis", fett=True),
    V.CfRegel(("ziel_rendite_override",), f'AND({{wohnflaeche_m2$}}<>"",NOT({WEG_RENDITE}))', V.FARBE_INAKTIV, "wirkt nur im Rendite-Weg", schrift=V.SCHRIFT_INAKTIV),
    V.CfRegel(("ziel_cf_override",), f'AND({{wohnflaeche_m2$}}<>"",{WEG_CF})', V.FARBE_AKTIV, "Ziel-Cashflow je WE bestimmt den Preis", fett=True),
    V.CfRegel(("ziel_cf_override",), f'AND({{wohnflaeche_m2$}}<>"",NOT({WEG_CF}))', V.FARBE_INAKTIV, "wirkt nur im Cashflow-Weg", schrift=V.SCHRIFT_INAKTIV),
    V.CfRegel((), "TRUE", V.FARBE_AKTIV, "Schalter Eingabe-Weg", param_keys=("eingabe_modus",), fett=True),
    V.CfRegel((), WEG_RENDITE, V.FARBE_AKTIV, "globale Ziel-Rendite aktiv", param_keys=("ziel_rendite",), fett=True),
    V.CfRegel((), f"NOT({WEG_RENDITE})", V.FARBE_INAKTIV, "globale Ziel-Rendite wirkt nicht", param_keys=("ziel_rendite",), schrift=V.SCHRIFT_INAKTIV),
    V.CfRegel((), WEG_CF, V.FARBE_AKTIV, "globaler Ziel-Cashflow aktiv", param_keys=("ziel_cf",), fett=True),
    V.CfRegel((), f"NOT({WEG_CF})", V.FARBE_INAKTIV, "globaler Ziel-Cashflow wirkt nicht", param_keys=("ziel_cf",), schrift=V.SCHRIFT_INAKTIV),
    V.CfRegel(("preis_quelle",), 'OR({preis_quelle}="Regler (Rückfall)",{preis_quelle}="kein Preis")', V.CF_ORANGE, "Rueckfall auf den Regler bzw. kein Preis"),
    V.CfRegel(("kaltmiete",), 'AND(ISNUMBER({kaltmiete_override}),{kaltmiete_override}>{MIETER!J})', V.CF_ORANGE, "Ist-Miete manuell angehoben"),
    V.CfRegel(("bewirtschaftungsquote_schaetzung",), 'AND({wohnflaeche_m2$}<>"",{bewirtschaftungsquote_schaetzung}<>"",{hausgeld_nicht_umlagefaehig}<>"")', V.CF_WARNROT, "zwei Hausgeld-Quellen"),
    V.CfRegel(("gebaeude_anteil_effektiv",), 'AND(ISNUMBER({gebaeude_anteil_effektiv}),{gebaeude_anteil_effektiv}<=0)', V.CF_WARNROT, "Bodenwert >= Kaufpreis"),
    V.CfRegel(("eigenkapital",), 'AND(ISNUMBER({eigenkapital}),{eigenkapital}>0.005,{p:finanzierungsfall}=2)', V.CF_ORANGE, "Eigenkapital trotz 'alles finanziert'"),
]

# ---------------------------------------------------------------- Datenpruefung (allow_blank ueberall: leer = Standard)
DV_REGELN: list = [
    V.DvRegel(("leerstand",), "list", formula1='"ja,nein"'),
    V.DvRegel((), "list", formula1='"1,2,3"', param_keys=("eingabe_modus",)),
    V.DvRegel(("ziel_rendite_override",), "decimal", "between", "0.005", "0.5", param_keys=("ziel_rendite",)),
    V.DvRegel(("ziel_cf_override",), "decimal", "between", "-10000", "10000", param_keys=("ziel_cf",)),
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
