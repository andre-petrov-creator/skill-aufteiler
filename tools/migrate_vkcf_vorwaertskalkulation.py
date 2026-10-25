#!/usr/bin/env python3
"""Template-Migration: Reiter "Verkauf Cashflow" auf die Vorwaertskalkulation je Wohnung (Layout 2).

Lauf:   python tools/migrate_vkcf_vorwaertskalkulation.py [--source TEMPLATE] [--target OUT] [--apply]

Ohne --apply wird NIE das Template angefasst: das Ergebnis landet in --target
(Default: template/Kalkulation_Aufteiler_mit_VK_CF.NEU.xlsx). Mit --apply wird zuerst ein Backup unter
template/backup/ angelegt, dann die Zieldatei ueber eine Temp-Datei atomar ersetzt.

Layout 2 (Andre, 2026-09-11): Zeile 1 Blocknamen, Zeile 2 Spaltenkoepfe, Wohnungen ab Zeile 3, Summe 23,
darunter Parameterbloecke (Kaeuferprofil | Objekt/Assets) und die Alt-Kontrollsektionen ab 41.
Layout 3 (2026-10-25): dritter Parameterblock EINGABE-WEG rechts, Legende links unten (Zeile 36-40),
Zins-Sensitivitaet und Text-Ampel unterhalb von Zeile 40 werden geleert (V.ENTFERNTE_BEREICHE).
Fixiert: zwei Kopfzeilen + Stammspalten bis Wohnflaeche. Design hell und ruhig (Pastellbloecke, Zebra).
Alle Adressen kommen aus tools/vkcf_vertrag.py; zweiter Lauf = identisches Ergebnis (Idempotenz).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vkcf_vertrag as V  # noqa: E402
from verify_vkcf_vorwaertskalkulation import inventar  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "template" / "Kalkulation_Aufteiler_mit_VK_CF.xlsx"
BACKUP_DIR = REPO_ROOT / "template" / "backup"

LAY = V.LAYOUT
NO_FILL = PatternFill(fill_type=None)
THIN = Side(style="thin", color=V.FARBE_RAHMEN)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BORDER_TOP = Border(top=Side(style="thin", color="FF808080"))


def fill(argb: str) -> PatternFill:
    return PatternFill("solid", start_color=argb, end_color=argb)


def font(size: float = 10, bold: bool = False, color: str = V.FARBE_TEXT) -> Font:
    return Font(name=V.SCHRIFT, size=size, bold=bold, color=color)


def check_writable(path: Path) -> None:
    if path.exists():
        try:
            with open(path, "r+b"):
                pass
        except OSError as e:
            raise SystemExit(f"Datei ist gesperrt (Excel offen? OneDrive?): {path} - {e}")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")


# ---------------------------------------------------------------- Aufraeumen
def clear_area(ws, vt: V.Vertrag) -> None:
    """Alles oberhalb der Bestandssektionen leeren: alter Titel/Parameter/Legende (1-16), alter Block (17-38)
    bzw. bei Layout-2-Vorlaeufer alles bis zur Parameterblock-Unterkante. Bestandssektionen ab Zeile 41 bleiben."""
    last_col = max(len(vt), ws.max_column, 14)
    top_end = 40
    # Merges loesen: alles oberhalb der Bestandssektionen und alle Baender, die ueber Spalte N hinausreichen
    # (Layout-1-Vorlaeufer hatte A41:CH41 / A53:CH53) - die Bestandsbaender A:N setzt write_layout neu
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row <= top_end or rng.max_col > 14:
            ws.unmerge_cells(str(rng))
    for row in range(1, top_end + 1):
        ws.row_dimensions[row].height = None
        for col in range(1, last_col + 1):
            c = ws.cell(row=row, column=col)
            c.value = None
            c.comment = None
            c.number_format = "General"
            c.fill = NO_FILL
            c.border = Border()
            c.font = font()
            c.alignment = Alignment()
    ws.conditional_formatting = type(ws.conditional_formatting)()
    ws.data_validations.dataValidation = []
    for col in range(1, last_col + 1):
        letter = get_column_letter(col)
        if col > len(vt):
            # weggefallene Spalten (Layout 2 -> 3): Breite/Outline auf Excel-Standard zuruecksetzen
            ws.column_dimensions.pop(letter, None)
            continue
        d = ws.column_dimensions[letter]
        d.outline_level = 0
        d.hidden = False
    clear_entfernte_bereiche(ws)


def clear_entfernte_bereiche(ws) -> None:
    """Alt-Kontrollen unterhalb von Zeile 40, die mit Kontrollspalten/Ampel entfallen (Layout 3)."""
    from openpyxl.utils.cell import range_boundaries
    for bereich in V.ENTFERNTE_BEREICHE:
        c1, r1, c2, r2 = range_boundaries(bereich)
        for rng in list(ws.merged_cells.ranges):
            if rng.min_row <= r2 and rng.max_row >= r1 and rng.min_col <= c2 and rng.max_col >= c1:
                ws.unmerge_cells(str(rng))
        for row in range(r1, r2 + 1):
            for col in range(c1, c2 + 1):
                c = ws.cell(row=row, column=col)
                c.value = None
                c.comment = None
                c.number_format = "General"
                c.fill = NO_FILL
                c.border = Border()
                c.font = font()


# ---------------------------------------------------------------- Datenblock
def write_block(ws, vt: V.Vertrag) -> None:
    # Zeile 1: Blocknamen ueber ihren Spalten (gemerged), Zeile 2: Koepfe
    start = 0
    spalten = vt.spalten
    for block in V.BLOCK_REIHENFOLGE:
        idx = [i for i, s in enumerate(spalten) if s.block == block]
        if not idx:
            continue
        a, b = get_column_letter(idx[0] + 1), get_column_letter(idx[-1] + 1)
        ws.merge_cells(f"{a}{LAY.block_row}:{b}{LAY.block_row}")
        c = ws[f"{a}{LAY.block_row}"]
        c.value = block.upper()
        c.fill = fill(V.BLOCK_FARBEN[block])
        c.font = font(10, True)
        c.alignment = Alignment(horizontal="center", vertical="center")
        start = idx[-1] + 1
    ws.row_dimensions[LAY.block_row].height = 20
    ws.row_dimensions[LAY.header_row].height = 44

    for i, sp in enumerate(spalten, start=1):
        col = get_column_letter(i)
        h = ws[f"{col}{LAY.header_row}"]
        h.value = sp.kopf
        h.fill = fill(V.BLOCK_FARBEN[sp.block])
        h.font = font(9, True)
        h.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        h.border = BORDER
        if sp.kommentar:
            h.comment = Comment(sp.kommentar, "Aufteiler-Skill")
        ws.column_dimensions[col].width = sp.breite
        for row in range(LAY.first, LAY.last + 1):
            c = ws[f"{col}{row}"]
            zebra = (row - LAY.first) % 2 == 1
            if sp.typ == "konstante":
                c.value = row - LAY.first + 1
                c.font = font()
                c.fill = fill(V.FARBE_ZEBRA) if zebra else NO_FILL
            elif sp.typ == "formel":
                c.value = vt.render(sp.formel, row)
                c.font = font()
                c.fill = fill(V.FARBE_ZEBRA) if zebra else NO_FILL
            else:  # eingabe / export: leer ist None, nie "" oder 0
                c.value = None
                c.font = font(10, False, "FF1F4E79")
                c.fill = fill(V.FARBE_EINGABE)
            c.number_format = sp.format
            c.border = BORDER
        s = ws[f"{col}{LAY.sum_row}"]
        s.value = vt.render(sp.summe, LAY.sum_row) if sp.summe else None
        s.number_format = sp.format
        s.font = font(10, True)
        s.fill = fill(V.FARBE_SUMME)
        s.border = BORDER_TOP
    ws[f"A{LAY.sum_row}"].value = V.SUM_LABEL


# ---------------------------------------------------------------- Parameterbloecke + Legende
def write_parameter(ws, vt: V.Vertrag) -> None:
    r0 = LAY.param_title_row
    for g, cfg in V.PARAM_GRUPPEN.items():
        a, b = cfg["label_col"], cfg["wert_col"]
        ws.merge_cells(f"{a}{r0}:{b}{r0}")
        t = ws[f"{a}{r0}"]
        t.value = cfg["titel"]
        t.fill = fill(V.FARBE_PARAM_TITEL)
        t.font = font(10, True)
        t.alignment = Alignment(vertical="center")
    ws.row_dimensions[r0].height = 20
    for p in vt.parameter:
        cell = vt.param_cell(p.key)
        lc = vt.param_label_cell(p.key)
        if lc:
            if p.gruppe != "fest":
                ws.merge_cells(vt.param_label_merge(p.key))
            ws[lc].value = p.label
            ws[lc].font = font(9)
            ws[lc].alignment = Alignment(vertical="center", wrap_text=True)
        c = ws[cell]
        c.value = vt.render(p.formel, LAY.sum_row) if p.formel else p.wert
        c.number_format = p.format
        c.font = font(10, False, "FF1F4E79" if p.eingabe else V.FARBE_TEXT)
        c.fill = fill(V.FARBE_EINGABE) if p.eingabe else NO_FILL
        c.border = BORDER
        c.alignment = Alignment(vertical="center")
        c.comment = Comment(p.kommentar, "Aufteiler-Skill") if p.kommentar else None
        if p.gruppe != "fest":
            ws.row_dimensions[int(cell[len(PARAM_WERT_COL(p.gruppe)):])].height = 24
    # Legende links unten: Farbfeld mit Stichwort | Erklaerung
    for i, e in enumerate(V.LEGENDE):
        r = V.LEGENDE_FIRST_ROW + i
        sw = ws[f"{V.LEGENDE_COL}{r}"]
        sw.value = e.stichwort
        sw.fill = fill(e.farbe) if e.farbe else NO_FILL
        sw.font = font(9, True, "FF1F4E79" if e.farbe == V.FARBE_EINGABE else V.FARBE_TEXT)
        sw.border = BORDER
        sw.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(f"{V.LEGENDE_TEXT_COL}{r}:{V.LEGENDE_MERGE_TO}{r}")
        t = ws[f"{V.LEGENDE_TEXT_COL}{r}"]
        t.value = e.text
        t.font = font(9)
        t.alignment = Alignment(vertical="center")
        ws.row_dimensions[r].height = 18


def PARAM_WERT_COL(gruppe: str) -> str:
    return V.PARAM_GRUPPEN[gruppe]["wert_col"]


# ---------------------------------------------------------------- Layout, Regeln, Mitzieher
def write_layout(ws, vt: V.Vertrag) -> None:
    for rng in V.BESTAND_MERGES:
        if rng not in {str(m) for m in ws.merged_cells.ranges}:
            ws.merge_cells(rng)
    freeze_col = get_column_letter([s.schluessel for s in vt.spalten].index(V.FREEZE_AFTER_KEY) + 2)
    ws.freeze_panes = f"{freeze_col}{LAY.first}"
    keys = [s.schluessel for s in vt.spalten]
    for first_key, last_key in V.GRUPPEN:
        for idx in range(keys.index(first_key), keys.index(last_key) + 1):
            d = ws.column_dimensions[get_column_letter(idx + 1)]
            d.outline_level = 1
            d.hidden = True
    ws.sheet_format.outlineLevelCol = 1
    ws.sheet_properties.outlinePr.summaryRight = False
    ws.sheet_view.showGridLines = False


def write_rules(ws, vt: V.Vertrag) -> None:
    for r in V.CF_REGELN:
        schrift = Font(color=r.schrift, bold=r.fett) if (r.schrift or r.fett) else None
        formel = vt.render(r.formel, LAY.first)[1:]
        bereiche = [f"{vt.letter[k]}{LAY.first}:{vt.letter[k]}{LAY.last}" for k in r.bereich_keys]
        bereiche += [vt.param_cell(k) for k in r.param_keys]
        for rng in bereiche:
            ws.conditional_formatting.add(rng, FormulaRule(formula=[formel], fill=fill(r.farbe), font=schrift))
    for d in V.DV_REGELN:
        # showErrorMessage: sonst nimmt Excel jede Eingabe still an (Schalter 2,5 zeigte "Rendite", rechnete Regler)
        dv = DataValidation(type=d.typ, operator=d.operator, formula1=d.formula1, formula2=d.formula2, allow_blank=True,
                            showErrorMessage=True, errorTitle="Ungültige Eingabe", error="Bitte einen Wert im erlaubten Bereich eintragen (leer = Standard).")
        for key in d.bereich_keys:
            col = vt.letter[key]
            dv.add(f"{col}{LAY.first}:{col}{LAY.last}")
        for pk in d.param_keys:
            dv.add(vt.param_cell(pk))
        ws.add_data_validation(dv)


def write_mitzieher(wb, vt: V.Vertrag) -> None:
    for m in V.MITZIEHER:
        ws = wb[m.sheet]
        row = m.row if m.row is not None else LAY.sum_row
        prefix = f"'{V.SHEET}'!" if m.sheet != V.SHEET else ""
        ws[m.zelle].value = vt.render(m.formel, row, prefix)
    for lb in V.LABELS:
        c = wb[lb.sheet][lb.zelle]
        c.value = lb.text
        if lb.kommentar:
            c.comment = Comment(lb.kommentar, "Aufteiler-Skill")
    for sheet, zelle in V.DATUMSZELLEN:
        wb[sheet][zelle].number_format = V.FMT_DATE


def set_markers(wb) -> None:
    for name in (V.VERSION_MARKER, V.LAYOUT_MARKER):
        if name in wb.defined_names:
            del wb.defined_names[name]
    wb.defined_names[V.VERSION_MARKER] = DefinedName(V.VERSION_MARKER, attr_text=f"'{V.SHEET}'!$A$1")
    wb.defined_names[V.LAYOUT_MARKER] = DefinedName(V.LAYOUT_MARKER, attr_text=str(V.LAYOUT_VERSION))


def patch_outline_level(xlsx: Path, sheet_title: str) -> None:
    """openpyxl 3.1.5 verwirft sheetFormatPr.outlineLevelCol beim Speichern - ohne das Attribut zeigt Excel
    die +/- Schaltflaechen nicht. Deshalb wird das Sheet-XML nach dem Speichern ergaenzt (idempotent)."""
    with zipfile.ZipFile(xlsx) as z:
        wbx = z.read("xl/workbook.xml").decode()
        rels = z.read("xl/_rels/workbook.xml.rels").decode()
        rid = dict(re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wbx))[sheet_title]
        m = re.search(r'<Relationship[^>]*Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or \
            re.search(r'<Relationship[^>]*Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
        target = m.group(1).lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        xml = z.read(target).decode()
        if 'outlineLevelCol="1"' not in xml:
            xml = re.sub(r"<sheetFormatPr\b", '<sheetFormatPr outlineLevelCol="1"', xml, count=1)
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
    tmp = xlsx.with_suffix(".patch.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for info, data in entries:
            out.writestr(info, xml.encode() if info.filename == target else data)
    os.replace(tmp, xlsx)


def migrate(source: Path, target: Path) -> None:
    vt = V.vertrag()
    fd, tmp_name = tempfile.mkstemp(suffix=".xlsx", dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copyfile(source, tmp)
        wb = openpyxl.load_workbook(tmp)
        ws = wb[V.SHEET]
        clear_area(ws, vt)
        write_block(ws, vt)
        write_parameter(ws, vt)
        write_layout(ws, vt)
        write_rules(ws, vt)
        write_mitzieher(wb, vt)
        set_markers(wb)
        wb.save(tmp)
        patch_outline_level(tmp, V.SHEET)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=str(TEMPLATE))
    ap.add_argument("--target", default=str(TEMPLATE.with_suffix(".NEU.xlsx")))
    ap.add_argument("--apply", action="store_true", help="Ergebnis ueber das Template legen (Backup vorher)")
    args = ap.parse_args()
    source = Path(args.source)
    target = Path(args.target) if not args.apply else source
    check_writable(target)
    if args.apply:
        BACKUP_DIR.mkdir(exist_ok=True)
        backup = BACKUP_DIR / f"{source.stem}_{stamp()}{source.suffix}"
        shutil.copy2(source, backup)
        print(f"Backup: {backup}")
        source = backup
    inv_vorher = inventar(source)
    migrate(source, target)
    inv_nachher = inventar(target)
    print(f"Geschrieben: {target}")
    print(f"Sheets vorher/nachher: {len(inv_vorher)}/{len(inv_nachher)} | "
          f"'{V.SHEET}' belegte Zellen {inv_vorher[V.SHEET]['n']} -> {inv_nachher[V.SHEET]['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
