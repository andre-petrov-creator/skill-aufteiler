"""Spaltenvertrag des Reiters "Verkauf Cashflow" (Vorwaertskalkulation je Wohnung).

Einzige Quelle der Wahrheit fuer Migration (tools/migrate_vkcf_vorwaertskalkulation.py),
Abnahme (tools/verify_vkcf_vorwaertskalkulation.py), Export (tools/export_excel.py) und Doku
(tools/vkcf_handoff_md.py).

Regel aus der Fehlerkartei (ERR-2026-09-04-objektliste-feste-spaltenbuchstaben-nach-umbau):
Zellen werden NIE ueber feste Adressen angesprochen. Spalten haben einen stabilen Schluessel,
Parameter ebenfalls; Formeln werden mit Platzhaltern notiert und erst beim Bau in Adressen
uebersetzt. Das Layout (Kopfzeilen, Datenzeilen, Parameterblock) ist damit frei verschiebbar.

Platzhalter:
  {key}            Vertragsspalte, eigene Zeile              -> F3
  {key$}           spaltenabsolut                            -> $F3
  {key@first}      erste Datenzeile (relativ)                -> F3     (auch @last, @sum, @<n>)
  {key$@sum}       Summenzeile, absolut                      -> $F$23
  {MIETER!F}       Fremdblatt, Zeile mit Layout-Offset       -> MIETER!F8
  {p:zins}         Parameter, immer absolut                  -> $C$27

Layout seit 2026-09-11 (Andre): Tabelle ab Zeile 1 (Blocknamen), Zeile 2 Spaltenkoepfe, Wohnungen
ab Zeile 3, Summenzeile 23; Parameterbloecke und Alt-Kontrollsektionen darunter. Fixiert werden nur
die zwei Kopfzeilen und die Stammspalten bis Wohnflaeche.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- Layout
@dataclass(frozen=True)
class Layout:
    block_row: int          # Blocknamen (Stamm | Preis | ...)
    header_row: int         # Spaltenkoepfe
    first: int              # erste Datenzeile
    last: int               # letzte Datenzeile (20 WE)
    sum_row: int            # Summenzeile
    mieter_row_of_first: int          # MIETER-Zeile der ersten WE (Bestand: 8)
    verkaufsmatrix_row_of_first: int  # VERKAUFSMATRIX-Zeile der ersten WE (Bestand: 6)
    param_title_row: int    # Ueberschrift des Parameterblocks
    param_first_row: int    # erste Parameterzeile
    param_cells: dict | None = None   # feste Adressen je Parameter-Key (nur fuer Legacy-Import)

    @property
    def offsets(self) -> dict[str, int]:
        return {"MIETER": self.mieter_row_of_first - self.first,
                "VERKAUFSMATRIX": self.verkaufsmatrix_row_of_first - self.first}

    def row_symbol(self, r: int) -> str:
        return {self.first: "first", self.last: "last", self.sum_row: "sum"}.get(r, str(r))

    def row_of(self, sym: str) -> int:
        return {"first": self.first, "last": self.last, "sum": self.sum_row}.get(sym) or int(sym)


LAYOUT = Layout(block_row=1, header_row=2, first=3, last=22, sum_row=23,
                mieter_row_of_first=8, verkaufsmatrix_row_of_first=6,
                param_title_row=25, param_first_row=26)

# Layout der Revisions-Runde (r1/r2-JSON): Kopf 17, Daten 18-37, Summe 38, Parameter in C5..C15 / N5..N14
LEGACY_PARAM_CELLS = {
    "zins": "C5", "tilgung": "C6", "steuersatz": "C7", "bewirt_quote_alt": "C8", "afa_satz_std": "C9",
    "gebaeude_anteil_std": "C10", "ziel_cf": "C11", "finanzierungsfall": "C12", "loan_faktor": "C13",
    "k_faktor_alt": "C14", "knk": "C15",
    "provision_std": "N5", "grundstueck_qm": "N6", "brw": "N7", "mea_nenner": "N8", "bodenwert_haus": "N9",
    "afa_garage": "N10", "afa_stellplatz": "N11", "ampel_toleranz": "N12", "loan_faktor_vorwaerts": "N13",
    "sperrfrist_monate": "N14",
    "kp_assets_gesamt": "C45", "verwaltung_eur_we_monat": "C62", "anzahl_we": "C63",
    "ruecklage_eur_qm_jahr": "C64", "wohnflaeche_gesamt": "C65", "nkm_jahr": "C69",
}
LAYOUT_LEGACY = Layout(block_row=16, header_row=17, first=18, last=37, sum_row=38,
                       mieter_row_of_first=8, verkaufsmatrix_row_of_first=6,
                       param_title_row=4, param_first_row=5, param_cells=LEGACY_PARAM_CELLS)

# Parameter-Gruppen und ihre Spalten im Block unter der Tabelle (Label | Wert)
PARAM_GRUPPEN = {
    "kaeufer": {"label_col": "A", "label_merge_to": "B", "wert_col": "C", "titel": "KÄUFER-PROFIL (Standard für alle Wohnungen — je Wohnung überschreibbar)"},
    "objekt": {"label_col": "E", "label_merge_to": "G", "wert_col": "H", "titel": "OBJEKT, ASSETS, STEUERUNG"},
}
LEGENDE_COL = "J"          # Legende rechts neben den Parametern (J:N gemerged, ab param_first_row)
LEGENDE_MERGE_TO = "N"

# ---------------------------------------------------------------- Zahlenformate (Template-Schreibweise, ohne rotes Minus)
FMT_EUR = '#,##0" €"'
FMT_EUR2 = '#,##0.00" €"'
FMT_EUR_QM = '#,##0" €/m²"'
FMT_EUR2_QM = '#,##0.00" €/m²"'
FMT_PCT = "0.00%"
FMT_PCT1 = "0.0%"
FMT_DATE = "dd\\.mm\\.yyyy"
FMT_INT = "0"
FMT_QM = "0.00"


# ---------------------------------------------------------------- Dataclasses
@dataclass(frozen=True)
class Spalte:
    schluessel: str
    kopf: str
    block: str
    typ: str                      # "eingabe" | "formel" | "konstante" | "export"
    formel: str | None = None     # mit Platzhaltern, ohne fuehrendes "="
    summe: str | None = None      # Formel der Summenzeile, ebenfalls mit Platzhaltern
    format: str = "General"
    breite: float = 11.0
    gruppiert: bool = False       # Hilfsspalte, per Outline eingeklappt
    crm_feld: str = "-"
    quelle_state: str = "-"
    kommentar: str | None = None


@dataclass(frozen=True)
class Parameter:
    key: str
    label: str
    gruppe: str                   # "kaeufer" | "objekt" | "fest"
    wert: object = None           # Konstante (None = Eingabe leer) ...
    formel: str | None = None     # ... oder Formel mit Platzhaltern
    format: str = "General"
    eingabe: bool = False         # hell hinterlegt, Datenpruefung
    kommentar: str | None = None
    zelle: str | None = None      # nur gruppe="fest": Bestandszelle (z.B. C62), bleibt wo sie ist
    label_zelle: str | None = None


@dataclass(frozen=True)
class Mitzieher:
    """Eine Bestandszelle ausserhalb des Datenblocks, deren Formel auf den Block oder Parameter zeigt."""
    sheet: str
    zelle: str
    formel: str                   # Platzhalter; {key} bezieht sich auf die VKCF-Zeile `row`
    row: int | None = None        # VKCF-Datenzeile (None = nur @sum-/Parameter-Bezuege)
    warum: str = ""


@dataclass(frozen=True)
class Label:
    sheet: str
    zelle: str
    text: str
    kommentar: str | None = None


@dataclass(frozen=True)
class CfRegel:
    bereich_keys: tuple[str, ...]
    formel: str                    # Platzhalter, relativ zur ersten Datenzeile
    farbe: str                     # ARGB, wird als start_color UND end_color gesetzt
    zweck: str = ""


@dataclass(frozen=True)
class DvRegel:
    bereich_keys: tuple[str, ...]
    typ: str                       # "decimal" | "whole" | "list"
    operator: str | None = None
    formula1: str | None = None
    formula2: str | None = None
    param_keys: tuple[str, ...] = ()   # zusaetzliche Parameterzellen (ueber Schluessel)


def column_letter(index: int) -> str:
    letters = ""
    while index > 0:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def column_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


# ---------------------------------------------------------------- Vertrag (Renderer)
class Vertrag:
    _PLATZHALTER = re.compile(r"\{([a-z0-9_]+)(\$?)(?:@([a-z]+|\d+))?\}")
    _FREMD = re.compile(r"\{(MIETER|VERKAUFSMATRIX)!(\$?[A-Z]{1,3})\}")
    _PARAM = re.compile(r"\{p:([a-z0-9_]+)\}")

    def __init__(self, spalten: list[Spalte], parameter: list[Parameter] | None = None, layout: Layout = LAYOUT):
        keys = [s.schluessel for s in spalten]
        doppelt = {k for k in keys if keys.count(k) > 1}
        if doppelt:
            raise ValueError(f"doppelte Schluessel: {sorted(doppelt)}")
        self.spalten = spalten
        self.parameter = parameter or []
        self.layout = layout
        self.letter = {s.schluessel: column_letter(i + 1) for i, s in enumerate(spalten)}
        self.key_of_letter = {v: k for k, v in self.letter.items()}
        self._param_cells = self._layout_param_cells()
        self._key_of_param_cell = {v: k for k, v in self._param_cells.items()}

    # ---- Parameteradressen
    def _layout_param_cells(self) -> dict[str, str]:
        if self.layout.param_cells is not None:
            return dict(self.layout.param_cells)
        cells: dict[str, str] = {}
        counters = {g: 0 for g in PARAM_GRUPPEN}
        for p in self.parameter:
            if p.gruppe == "fest":
                cells[p.key] = p.zelle
            else:
                g = PARAM_GRUPPEN[p.gruppe]
                cells[p.key] = f"{g['wert_col']}{self.layout.param_first_row + counters[p.gruppe]}"
                counters[p.gruppe] += 1
        return cells

    def param_cell(self, key: str) -> str:
        if key not in self._param_cells:
            raise KeyError(f"unbekannter Parameter {{p:{key}}}")
        return self._param_cells[key]

    def param_label_cell(self, key: str) -> str | None:
        p = next(x for x in self.parameter if x.key == key)
        if p.gruppe == "fest":
            return p.label_zelle
        g = PARAM_GRUPPEN[p.gruppe]
        return f"{g['label_col']}{self.param_cell(key)[len(g['wert_col']):]}"

    def param_label_merge(self, key: str) -> str | None:
        p = next(x for x in self.parameter if x.key == key)
        if p.gruppe == "fest":
            return None
        g = PARAM_GRUPPEN[p.gruppe]
        r = self.param_cell(key)[len(g["wert_col"]):]
        return f"{g['label_col']}{r}:{g['label_merge_to']}{r}"

    # ---- Rendern
    def render(self, formel: str, row: int, sheet_prefix: str = "") -> str:
        """Platzhalter -> Zellbezug. Unbekannter Schluessel = harter Fehler, kein stilles Weiterlaufen."""
        lay = self.layout

        def repl(m: re.Match) -> str:
            key, absolut, fixed = m.group(1), m.group(2), m.group(3)
            if key not in self.letter:
                raise KeyError(f"unbekannter Spaltenschluessel {{{key}}} in Formel: {formel}")
            col = self.letter[key]
            if fixed:
                r = lay.row_of(fixed)
                ref = f"${col}${r}" if absolut else f"{col}{r}"
            else:
                ref = f"${col}{row}" if absolut else f"{col}{row}"
            return sheet_prefix + ref

        def repl_fremd(m: re.Match) -> str:
            sheet, col = m.group(1), m.group(2)
            return f"{sheet}!{col}{row + lay.offsets[sheet]}"

        def repl_param(m: re.Match) -> str:
            cell = self.param_cell(m.group(1))
            col = re.match(r"[A-Z]+", cell).group(0)
            return f"{sheet_prefix}${col}${cell[len(col):]}"

        out = formel.replace("{rowbase}", str(lay.first - 1))   # ROW()-{rowbase} = laufende Nummer ab 1
        out = self._PARAM.sub(repl_param, out)
        out = self._FREMD.sub(repl_fremd, out)
        return "=" + self._PLATZHALTER.sub(repl, out)

    def keys_in(self, formel: str) -> set[str]:
        return {m.group(1) for m in self._PLATZHALTER.finditer(formel)}

    # ---- Ruecksubstitution (Import + Abnahme)
    def ruecksubstitution(self, excel_formel: str, row: int | None, sheet_prefix: str = "") -> str:
        """Adressen -> Schluessel, fuer Import und Abnahme: 'gueltige Formel auf falscher Spalte' wird sichtbar.

        row = Datenzeile: Zellen dieser Zeile werden {key}, andere Datenblock-Zeilen {key@first|last|sum|n}.
        row = None (Parameter-/Summenformeln): jede Datenblock-Zeile wird {key@...}.
        Parameteradressen (laut Layout) werden {p:key}; alles andere bleibt Literal.
        """
        lay = self.layout
        s = excel_formel
        if sheet_prefix:
            s = s.replace(sheet_prefix, "\x00")

        def repl_fremd(m: re.Match) -> str:
            sheet, col_abs, col, r = m.group(1), m.group(2), m.group(3), m.group(4)
            if row is not None and not col_abs and int(r) == row + lay.offsets[sheet]:
                return f"{{{sheet}!{col}}}"
            return m.group(0)
        s = re.sub(r"(MIETER|VERKAUFSMATRIX)!(\$?)([A-Z]{1,3})\$?(\d+)", repl_fremd, s)

        def repl(m: re.Match) -> str:
            marker, col_abs, col, row_abs, r = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            rr = int(r)
            pkey = self._key_of_param_cell.get(f"{col}{rr}")
            if pkey is not None and (marker == "\x00" or not sheet_prefix):
                return f"{{p:{pkey}}}"
            key = self.key_of_letter.get(col)
            if key is None or not (lay.first <= rr <= lay.sum_row):
                return m.group(0)
            if sheet_prefix and marker != "\x00":
                return m.group(0)
            if row is None or rr != row:
                sym = lay.row_symbol(rr)
                return f"{{{key}$@{sym}}}" if (col_abs or row_abs) else f"{{{key}@{sym}}}"
            return f"{{{key}$}}" if col_abs else f"{{{key}}}"
        s = re.sub(r"(\x00?)(?<![!A-Z])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(])", repl, s)
        return s.replace("\x00", sheet_prefix)

    def __len__(self) -> int:
        return len(self.spalten)


# ---------------------------------------------------------------- Konstanten des Reiters
VERSION_MARKER = "AUFTEILER_TPL_V2"
LAYOUT_MARKER = "AUFTEILER_TPL_LAYOUT"   # Defined Name mit Layout-Version als Wert
LAYOUT_VERSION = 2
SHEET = "Verkauf Cashflow"
FREEZE_AFTER_KEY = "wohnflaeche_m2"      # Fixierung rechts von dieser Spalte
SUM_LABEL = "SUMME / Ø"
BLOCK_REIHENFOLGE = ("Stamm", "Preis", "Miete", "Bewirtschaftung", "Steuer", "Ergebnis")

# Design (hell, augenschonend) - Farben je Block fuer Blockzeile + Koepfe
BLOCK_FARBEN = {
    "Stamm": "FFE7E6E6", "Preis": "FFDDEBF7", "Miete": "FFE2EFDA",
    "Bewirtschaftung": "FFFFF2CC", "Steuer": "FFE4DFEC", "Ergebnis": "FFFCE4D6",
}
FARBE_EINGABE = "FFFFFBE6"      # sehr helles Gelb
FARBE_ZEBRA = "FFF7F7F7"
FARBE_SUMME = "FFEDEDED"
FARBE_RAHMEN = "FFD9D9D9"
FARBE_PARAM_TITEL = "FFDDEBF7"
FARBE_TEXT = "FF404040"
SCHRIFT = "Calibri"

# Ampel-/Warnfarben (Excel-Standard "Gut/Neutral/Schlecht")
AMPEL_GRUEN, AMPEL_GELB, AMPEL_ROT, AMPEL_GRAU = "FFC6EFCE", "FFFFEB9C", "FFFFC7CE", "FFEDEDED"
CF_MINT, CF_GELB, CF_ORANGE, CF_WARNROT = "FFE2EFDA", "FFFFF2CC", "FFFFE0B2", "FFFFC7CE"

# Bestands-Sektionen unter dem Parameterblock (bleiben an Ort und Stelle)
BESTAND_MERGES = ("A41:N41", "A53:N53")

# Werden aus vkcf_vertrag_daten / vkcf_vertrag_hand befuellt; leer = noch kein Vertrag.
SPALTEN: list[Spalte] = []
PARAMETER: list[Parameter] = []
MITZIEHER: list[Mitzieher] = []
LABELS: list[Label] = []
LEGENDE: list[str] = []
CF_REGELN: list[CfRegel] = []
DV_REGELN: list[DvRegel] = []
GRUPPEN: list[tuple[str, str]] = []
ERLAUBTE_AENDERUNGEN: set[tuple[str, str]] = set()
DATUMSZELLEN: list[tuple[str, str]] = []


try:  # generierte + handgepflegte Vertragsdaten
    from vkcf_vertrag_daten import *  # noqa: F401,F403
except ImportError:
    pass


def vertrag(layout: Layout = LAYOUT) -> Vertrag:
    if not SPALTEN:
        raise RuntimeError("SPALTEN ist leer - tools/vkcf_vertrag_daten.py fehlt (Generator: tools/vkcf_vertrag_import.py).")
    return Vertrag(SPALTEN, PARAMETER, layout)
