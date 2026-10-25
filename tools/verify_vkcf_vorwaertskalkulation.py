#!/usr/bin/env python3
"""Abnahme des Reiters "Verkauf Cashflow" (Vorwaertskalkulation je Wohnung, Layout 2).

Lauf:   python tools/verify_vkcf_vorwaertskalkulation.py --file <migriert.xlsx> [--source <original.xlsx>]
                                                          [--fixtures tools/fixtures/vkcf_referenz.json] [--calc] [--export]

Prueft den VERTRAG (Struktur, Formeln, Typen, Formate, Fixierung, Gruppierung, Regeln), nie Nutzerwerte
(Vault: ERR-2026-09-04-objektliste-pruefer-verdrahtet-user-werte). Drei Stufen:
  1. verify_contract  - jede Zelle des Blocks und des Parameterblocks gegen tools/vkcf_vertrag.py, inkl.
                        Ruecksubstitution Adresse -> Schluessel (faengt "gueltige Formel auf falscher Spalte")
  2. verify_lossless  - Roundtrip gegen das Original: ausserhalb des Reiters und der erlaubten
                        Mitzieher darf sich KEINE Zelle geaendert haben
  3. verify_calc      - Fixtures in eine Kopie schreiben, mit `formulas` rechnen (kein Excel noetig),
                        Erwartungswerte je Schluessel vergleichen (--calc, ~90 s je Lauf)
--export: Datei ist ein befuellter Objekt-Export (tools/export_excel.py) statt des leeren Templates -
          Eingabezellen und Eingabe-Parameter duerfen Werte tragen (nur Typ wird geprueft), die Rechenlaeufe
          setzen vorher alle Eingaben auf den Template-Stand zurueck.
Konsolenausgabe ASCII (Windows cp1252).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vkcf_vertrag as V  # noqa: E402

LAY = V.LAYOUT
FAILS: list[str] = []
PASSES = 0


def check(label: str, ok: bool, detail: str = "") -> bool:
    global PASSES
    if ok:
        PASSES += 1
    else:
        FAILS.append(f"{label}{(' - ' + detail) if detail else ''}")
    return ok


# ---------------------------------------------------------------- Inventar / Roundtrip
def _norm(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()[:19]
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def inventar(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=False)
    out = {}
    for ws in wb.worksheets:
        cells = {}
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    cells[c.coordinate] = (_norm(c.value), c.number_format)
        out[ws.title] = {
            "n": len(cells),
            "cells": cells,
            "merged": sorted(str(m) for m in ws.merged_cells.ranges),
            "freeze": ws.freeze_panes,
            "cf": sum(len(r.rules) for r in ws.conditional_formatting),
            "dv": len(ws.data_validations.dataValidation),
            "hidden_cols": sorted(k for k, d in ws.column_dimensions.items() if d.hidden),
            "widths": {k: d.width for k, d in ws.column_dimensions.items() if d.width},
            "comments": sorted(c.coordinate for row in ws.iter_rows() for c in row if c.comment),
        }
    return out


def verify_lossless(target: Path, source: Path) -> None:
    a, b = inventar(source), inventar(target)
    check("Roundtrip: gleiche Sheets", list(a) == list(b), f"{list(a)} vs {list(b)}")
    for name in a:
        if name not in b or name == V.SHEET:
            continue
        erlaubt = {z for s, z in V.ERLAUBTE_AENDERUNGEN if s == name}
        ca, cb = a[name]["cells"], b[name]["cells"]
        verloren = [k for k in ca if k not in cb and k not in erlaubt]
        neu = [k for k in cb if k not in ca and k not in erlaubt]
        anders = [k for k in ca if k in cb and ca[k] != cb[k] and k not in erlaubt]
        check(f"Roundtrip {name}: nichts verloren", not verloren, ", ".join(verloren[:8]))
        check(f"Roundtrip {name}: nichts still hinzugefuegt", not neu, ", ".join(neu[:8]))
        check(f"Roundtrip {name}: nichts still geaendert", not anders, ", ".join(anders[:8]))
        for key in ("merged", "freeze", "cf", "dv", "hidden_cols"):
            check(f"Roundtrip {name}: {key} unveraendert", a[name][key] == b[name][key], f"{a[name][key]} vs {b[name][key]}")
        comm = set(a[name]["comments"]) ^ set(b[name]["comments"])
        check(f"Roundtrip {name}: Kommentare unveraendert (ausser erlaubte)", not (comm - erlaubt), ", ".join(sorted(comm - erlaubt)))
        for z in erlaubt:
            check(f"Mitzieher {name}!{z} gesetzt", z in cb, "Zelle fehlt nach Migration")


# ---------------------------------------------------------------- Vertrag
def _sheet_xml(path: Path, title: str) -> str:
    with zipfile.ZipFile(path) as z:
        wbx = z.read("xl/workbook.xml").decode()
        rels = z.read("xl/_rels/workbook.xml.rels").decode()
        rid = dict(re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wbx))[title]
        m = re.search(r'<Relationship[^>]*Id="%s"[^>]*Target="([^"]+)"' % rid, rels) or \
            re.search(r'<Relationship[^>]*Target="([^"]+)"[^>]*Id="%s"' % rid, rels)
        t = m.group(1).lstrip("/")
        return z.read(t if t.startswith("xl/") else "xl/" + t).decode()


def verify_contract(path: Path, export: bool = False) -> None:
    vt = V.vertrag()
    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb[V.SHEET]
    merges = {str(m) for m in ws.merged_cells.ranges}

    check("Versionsmarker vorhanden", V.VERSION_MARKER in wb.defined_names)
    check("Layoutmarker vorhanden", V.LAYOUT_MARKER in wb.defined_names and
          str(wb.defined_names[V.LAYOUT_MARKER].attr_text) == str(V.LAYOUT_VERSION), str(wb.defined_names.get(V.LAYOUT_MARKER)))

    # Blockzeile: Name ueber der ersten Spalte des Blocks, gemerged bis zur letzten
    for block in V.BLOCK_REIHENFOLGE:
        idx = [i for i, s in enumerate(vt.spalten) if s.block == block]
        if not idx:
            continue
        a, b = get_column_letter(idx[0] + 1), get_column_letter(idx[-1] + 1)
        check(f"Blockzeile {block}", ws[f"{a}{LAY.block_row}"].value == block.upper() and f"{a}{LAY.block_row}:{b}{LAY.block_row}" in merges,
              f"{ws[f'{a}{LAY.block_row}'].value!r}, merge {a}{LAY.block_row}:{b}{LAY.block_row} {'ok' if f'{a}{LAY.block_row}:{b}{LAY.block_row}' in merges else 'fehlt'}")

    for i, sp in enumerate(vt.spalten, start=1):
        col = get_column_letter(i)
        check(f"Kopf {col} = {sp.schluessel}", ws[f"{col}{LAY.header_row}"].value == sp.kopf, repr(ws[f"{col}{LAY.header_row}"].value))
        check(f"Breite {col}", ws.column_dimensions[col].width is not None)
        for row in (LAY.first, LAY.first + 1, LAY.last):
            c = ws[f"{col}{row}"]
            if sp.typ == "formel":
                soll = vt.render(sp.formel, row)
                ok = c.value == soll
                detail = f"ist {vt.ruecksubstitution(c.value, row)} | soll {sp.formel}" if (not ok and isinstance(c.value, str)) else repr(c.value)
                check(f"Formel {col}{row} ({sp.schluessel})", ok, detail)
            elif sp.typ == "konstante":
                check(f"Konstante {col}{row}", c.value == row - LAY.first + 1, repr(c.value))
            elif export:
                check(f"Eingabe {col}{row} kein Formel-Text", not (isinstance(c.value, str) and c.value.startswith("=")), repr(c.value))
            else:
                check(f"Eingabe {col}{row} leer (None)", c.value is None, repr(c.value))
            check(f"Format {col}{row}", c.number_format == sp.format, f"{c.number_format!r} != {sp.format!r}")
        s = ws[f"{col}{LAY.sum_row}"]
        soll_s = vt.render(sp.summe, LAY.sum_row) if sp.summe else (V.SUM_LABEL if sp is vt.spalten[0] else None)
        check(f"Summe {col}{LAY.sum_row} ({sp.schluessel})", s.value == soll_s,
              f"ist {vt.ruecksubstitution(str(s.value), LAY.sum_row) if s.value else None} | soll {sp.summe}")
    for col_idx in range(len(vt) + 1, len(vt) + 30):
        col = get_column_letter(col_idx)
        for row in range(LAY.block_row, LAY.sum_row + 1):
            if ws[f"{col}{row}"].value is not None:
                check(f"Rest rechts vom Block {col}{row}", False, repr(ws[f"{col}{row}"].value))
                break

    # Parameterbloecke
    for g, cfg in V.PARAM_GRUPPEN.items():
        t = f"{cfg['label_col']}{LAY.param_title_row}"
        check(f"Parameter-Titel {g}", ws[t].value == cfg["titel"] and f"{cfg['label_col']}{LAY.param_title_row}:{cfg['wert_col']}{LAY.param_title_row}" in merges, repr(ws[t].value))
    for p in vt.parameter:
        cell = vt.param_cell(p.key)
        c = ws[cell]
        soll = vt.render(p.formel, LAY.sum_row) if p.formel else p.wert
        if export and p.eingabe:
            check(f"Parameter {p.key} ({cell}) Zahl oder leer", c.value is None or isinstance(c.value, (int, float)), repr(c.value))
        else:
            check(f"Parameter {p.key} ({cell})", c.value == soll,
                  f"ist {vt.ruecksubstitution(str(c.value), None) if isinstance(c.value, str) else c.value!r} | soll {p.formel or p.wert!r}")
        if p.eingabe and c.value is not None:
            check(f"Parameter {p.key} ist Zahl, kein Text", isinstance(c.value, (int, float)), repr(c.value))
        check(f"Parameter {p.key} Format", c.number_format == p.format, f"{c.number_format!r} != {p.format!r}")
        lc = vt.param_label_cell(p.key)
        if lc:
            check(f"Label {p.key} ({lc})", ws[lc].value == p.label, repr(ws[lc].value))
            mg = vt.param_label_merge(p.key)
            if mg:
                check(f"Label-Merge {p.key}", mg in merges, mg)
    for i, text in enumerate(V.LEGENDE):
        r = LAY.param_first_row + i
        check(f"Legende Zeile {r}", ws[f"{V.LEGENDE_COL}{r}"].value == text and f"{V.LEGENDE_COL}{r}:{V.LEGENDE_MERGE_TO}{r}" in merges)

    # Layout
    freeze_col = get_column_letter([s.schluessel for s in vt.spalten].index(V.FREEZE_AFTER_KEY) + 2)
    check("Fixierung (2 Kopfzeilen + Stamm)", ws.freeze_panes == f"{freeze_col}{LAY.first}", str(ws.freeze_panes))
    for first_key, last_key in V.GRUPPEN:
        for key in (first_key, last_key):
            d = ws.column_dimensions[vt.letter[key]]
            check(f"Gruppierung {key}", d.outline_level >= 1 and d.hidden, f"level={d.outline_level} hidden={d.hidden}")
    xml = _sheet_xml(path, V.SHEET)
    check("sheetFormatPr outlineLevelCol=1 (Gruppierungs-Schaltflaechen)", 'outlineLevelCol="1"' in xml, re.search(r"<sheetFormatPr[^>]*/?>", xml).group(0))
    for rng in V.BESTAND_MERGES:
        check(f"Bestands-Merge {rng}", rng in merges)
    alt = [m for m in merges if int(re.search(r"(\d+)", m).group(1)) <= LAY.sum_row and not m.startswith(("A", "G", "L", "AG", "AW", "BE", "BS"))]
    n_cf = sum(len(r.rules) for r in ws.conditional_formatting)
    check("CF-Regeln vorhanden", n_cf >= sum(len(r.bereich_keys) for r in V.CF_REGELN), str(n_cf))
    for r in ws.conditional_formatting:
        for rule in r.rules:
            f = rule.dxf.fill if rule.dxf else None
            check(f"CF {r.sqref} hat end_color", f is not None and f.end_color is not None and f.end_color.rgb not in (None, "00000000"),
                  "Fuellung ohne end_color wird in Excel nicht angezeigt (ERR-2026-09-02)")
    for dv in ws.data_validations.dataValidation:
        check(f"DV {dv.sqref} allow_blank", bool(dv.allow_blank), "ohne allow_blank kippt 'leer = Standard'")
    for m in V.MITZIEHER:
        row = m.row if m.row is not None else LAY.sum_row
        prefix = f"'{V.SHEET}'!" if m.sheet != V.SHEET else ""
        c = wb[m.sheet][m.zelle]
        soll = vt.render(m.formel, row, prefix)
        check(f"Mitzieher {m.sheet}!{m.zelle}", c.value == soll, f"ist {vt.ruecksubstitution(str(c.value), row, prefix)} | soll {m.formel}")
    mieter = wb["MIETER"]
    for row in range(LAY.mieter_row_of_first, LAY.mieter_row_of_first + 20):
        for col in ("H", "I"):
            v = mieter[f"{col}{row}"].value
            check(f"MIETER!{col}{row} Datum oder leer", v is None or isinstance(v, (dt.date, dt.datetime)), repr(v))


# ---------------------------------------------------------------- Rechenabnahme
def verify_calc(path: Path, fixtures_path: Path, export: bool = False) -> None:
    import formulas  # lazy: Import dauert, nur bei --calc

    vt = V.vertrag()
    spec = json.loads(fixtures_path.read_text(encoding="utf-8"))
    tol_default = spec.get("toleranz_default", 0.5)
    for lauf in spec["laeufe"]:
        _verify_calc_lauf(path, vt, lauf, tol_default, formulas, export)


def _verify_calc_lauf(path: Path, vt, lauf: dict, tol_default: float, formulas, export: bool = False) -> None:
    """Ein Lauf = ein Parametersatz (Schluessel -> Wert); die Fixtures des Laufs liegen ab der ersten Datenzeile."""
    fd, tmp_name = tempfile.mkstemp(suffix=".xlsx", dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copyfile(path, tmp)
        wb = openpyxl.load_workbook(tmp)
        ws = wb[V.SHEET]
        if export:
            for p in vt.parameter:
                if p.eingabe:
                    ws[vt.param_cell(p.key)] = p.wert
            for row in range(LAY.first, LAY.last + 1):
                for sp in vt.spalten:
                    if sp.typ not in ("formel", "konstante"):
                        ws[f"{vt.letter[sp.schluessel]}{row}"] = None
        for key, val in lauf.get("parameter", {}).items():
            ws[vt.param_cell(key)] = val
        for cell, val in lauf.get("mieter_global", {}).items():
            wb["MIETER"][cell] = val
        for i, fx in enumerate(lauf["fixtures"]):
            row = LAY.first + i
            mrow = row + LAY.offsets["MIETER"]
            for cell, val in fx.get("mieter", {}).items():
                wb["MIETER"][f"{cell}{mrow}"] = dt.date.fromisoformat(val) if cell in ("H", "I") and val else val
            for key, val in fx.get("eingaben", {}).items():
                ws[f"{vt.letter[key]}{row}"] = val
        wb.save(tmp)
        book = f"[{tmp.name}]"
        sol = formulas.ExcelModel().loads(str(tmp)).finish().calculate()

        def get(sheet: str, cell: str):
            v = sol.get(f"'{book}{sheet.upper()}'!{cell}")
            try:
                return v.value[0][0]
            except Exception:
                return v

        for i, fx in enumerate(lauf["fixtures"]):
            row = LAY.first + i
            for key, exp in fx.get("erwartet", {}).items():
                if key not in vt.letter:
                    check(f"Rechnung {fx['name']} {key}", False, "Schluessel nicht im Vertrag")
                    continue
                ist = get(V.SHEET, f"{vt.letter[key]}{row}")
                tol = fx.get("toleranz", {}).get(key, tol_default)
                ok = isinstance(ist, (int, float)) and abs(float(ist) - float(exp)) <= tol
                check(f"Rechnung Lauf {lauf['lauf']} {fx['name'][:40]} {key}", ok, f"ist {ist!r} soll {exp} (tol {tol})")
        for cell, exp in lauf.get("erwartet_zellen", {}).items():
            if cell.startswith("p:"):
                sheet, addr = V.SHEET, vt.param_cell(cell[2:])
            else:
                sheet, addr = cell.split("!")
            ist = get(sheet.strip("'"), addr)
            check(f"Rechnung Lauf {lauf['lauf']} {cell}", isinstance(ist, (int, float)) and abs(float(ist) - float(exp)) <= tol_default, f"ist {ist!r} soll {exp}")

        # Fehlerwerte in den vom Umbau beruehrten Blaettern; MIETER nur in den WE-Zeilen (der Kennzahlenblock
        # ab Zeile 28 teilt in einer Fixture-Kopie mit 1-3 Zeilen durch 0 - Bestand). Ganz-Mappen-Pruefung = COM auf Export.
        mi_first, mi_last = LAY.mieter_row_of_first, LAY.mieter_row_of_first + 19

        def relevant(key: str) -> bool:
            m = re.search(r"\]([^']+)'!\$?([A-Z]+)\$?(\d+)$", key)
            if not m:
                return False
            sheet, row = m.group(1), int(m.group(3))
            if sheet == V.SHEET.upper() or sheet == "VERKAUFSMATRIX":
                return True
            return sheet == "MIETER" and mi_first <= row <= mi_last

        fehler = [k for k, v in sol.items() if relevant(k) and str(getattr(v, "value", "")).startswith("[[#")]
        check(f"Lauf {lauf['lauf']}: keine Excel-Fehlerwerte in Verkauf Cashflow/VERKAUFSMATRIX/MIETER-Datenzeilen", not fehler, ", ".join(sorted(fehler)[:8]))
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--source", help="Original vor der Migration (Roundtrip)")
    ap.add_argument("--fixtures", default=str(Path(__file__).parent / "fixtures" / "vkcf_referenz.json"))
    ap.add_argument("--calc", action="store_true", help="Rechenabnahme mit formulas (~90 s je Lauf)")
    ap.add_argument("--export", action="store_true", help="befuellter Objekt-Export statt leeres Template")
    args = ap.parse_args()
    target = Path(args.file)
    verify_contract(target, args.export)
    if args.source:
        verify_lossless(target, Path(args.source))
    if args.calc:
        verify_calc(target, Path(args.fixtures), args.export)
    print(f"{PASSES} Pruefungen bestanden, {len(FAILS)} fehlgeschlagen")
    for f in FAILS:
        print("  FAIL:", f.encode("ascii", "replace").decode())
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
