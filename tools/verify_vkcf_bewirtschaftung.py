#!/usr/bin/env python3
"""Recalc-Verifikation der Bewirtschaftungs-/Ruecklagen-Formeln im Reiter "Verkauf Cashflow".

Liest die ECHTEN Formel-Strings aus dem Template und wertet sie mit einem schlanken
eigenstaendigen Resolver aus (kein LibreOffice / kein pip noetig). Setzt ein Referenz-Objekt
(6 WE, 390 m2, Ist 6,00 EUR/m2, C64=14) als Overrides und prueft gegen die Soll-Werte
aus dem Sparring. Faengt Tippfehler in den Datei-Formeln (falsche Zellrefs etc.).

Lauf: python tools/verify_vkcf_bewirtschaftung.py
"""
import re
import math
import openpyxl

TEMPLATE = r"C:\meine-projekte\Immobilien\Aufteiler\template\Kalkulation_Aufteiler_mit_VK_CF.xlsx"

# Referenz-Objekt: 6 WE a 65 m2 = 390 m2, Ist 6,00 EUR/m2 -> 390 EUR/Mo je WE
WE_FLAECHE = [65.0] * 6
WE_MIETE_MO = [390.0] * 6   # 65 * 6,00


class Sheet:
    """Minimaler Excel-Resolver fuer eine Tabelle mit Overrides."""

    def __init__(self, ws, overrides):
        self.ws = ws
        self.overrides = overrides
        self.cache = {}

    def get(self, coord):
        coord = coord.replace("$", "")
        if coord in self.overrides:
            return self.overrides[coord]
        if coord in self.cache:
            return self.cache[coord]
        self.cache[coord] = 0  # cycle guard
        raw = self.ws[coord].value
        if isinstance(raw, str) and raw.startswith("="):
            val = self._eval(raw[1:])
        elif raw is None:
            val = ""
        else:
            val = raw
        self.cache[coord] = val
        return val

    def _range(self, ref):
        a, b = ref.split(":")
        cells = self.ws[f"{a}:{b}"]
        out = []
        for row in cells:
            for c in row:
                out.append(self.get(c.coordinate))
        return out

    def _eval(self, expr):
        expr = expr.replace("$", "")

        def repl_range(m):
            vals = self._range(m.group(0))
            return repr(vals)

        # ranges A77:B87 -> list literal
        expr = re.sub(r"[A-Z]+\d+:[A-Z]+\d+", repl_range, expr)

        # cell refs (not function names): letters+digits followed by non-(
        def repl_cell(m):
            return f"self.get('{m.group(0)}')"
        # function names are letters( -> protect by requiring digits in ref
        expr = re.sub(r"\b([A-Z]+\d+)\b", repl_cell, expr)

        # excel funcs -> python helpers
        expr = re.sub(r"\bIFERROR\(", "_iferror(", expr)
        expr = re.sub(r"\bMAX\(", "_max(", expr)
        expr = re.sub(r"\bMIN\(", "_min(", expr)
        expr = re.sub(r"\bSUM\(", "_sum(", expr)
        expr = re.sub(r"\bCOUNT\(", "_count(", expr)
        expr = re.sub(r"\bAVERAGE\(", "_avg(", expr)

        ns = {
            "self": self,
            "_iferror": lambda a, b: b if (a is None or a == "" or isinstance(a, float) and math.isnan(a)) else a,
            "_max": lambda *a: max(_flat_nums(a)) if _flat_nums(a) else 0,
            "_min": lambda *a: min(_flat_nums(a)) if _flat_nums(a) else 0,
            "_sum": lambda *a: sum(_flat_nums(a)),
            "_count": lambda *a: len(_flat_nums(a)),
            "_avg": lambda *a: (sum(_flat_nums(a)) / len(_flat_nums(a))) if _flat_nums(a) else 0,
        }
        try:
            return eval(expr, {"__builtins__": {}}, ns)
        except ZeroDivisionError:
            return float("nan")


def _flat_nums(args):
    out = []
    for a in args:
        seq = a if isinstance(a, (list, tuple)) else [a]
        for x in seq:
            if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
                out.append(x)
    return out


def approx(a, b, tol):
    return abs(a - b) <= tol


def main():
    wb = openpyxl.load_workbook(TEMPLATE)
    ws = wb["Verkauf Cashflow"]

    overrides = {}
    # Alle WE-Zeilen 18-37 overriden, damit der Resolver NIE die MIETER-referenzierenden
    # Datei-Formeln (IF/ISNUMBER/Cross-Sheet) auswerten muss. Belegt = Referenz-Objekt, Rest leer.
    for r in range(18, 38):
        idx = r - 18
        if idx < len(WE_FLAECHE):
            overrides[f"F{r}"] = WE_FLAECHE[idx]
            overrides[f"G{r}"] = WE_MIETE_MO[idx]
        else:
            overrides[f"F{r}"] = ""
            overrides[f"G{r}"] = ""
    # F38/G38 sind SUM-Formeln; der Resolver rechnet sie aus den Overrides.
    # C14 (k-Faktor) ist eine bestehende, unveraenderte Formel mit IF-Kette (C13);
    # als bekannter Kaeufer-Profil-Input gesetzt, damit der Resolver kein IF parsen muss.
    overrides["C14"] = (1 * (0.048 + 0.01) - 0.42 * 1 * 0.048 - 0.42 * 0.8 * 0.02) / 12

    s = Sheet(ws, overrides)

    results = {
        "C63 Anzahl WE": (s.get("C63"), 6, 0),
        "C65 Flaeche": (s.get("C65"), 390, 0.5),
        "C66 Verwaltung/J": (s.get("C66"), 2520, 1),
        "C67 Ruecklage/J": (s.get("C67"), 5460, 1),
        "C68 Ruecklage 10J": (s.get("C68"), 54600, 1),
        "C69 NKM/J": (s.get("C69"), 28080, 1),
        "C8 Quote": (s.get("C8"), 0.2842, 0.001),
        "C75 10J-Bedarf": (s.get("C75"), 54600, 1),
        "Topf0 D77 Quote": (s.get("D77"), 0.2842, 0.001),
        "Topf0 E77 VK": (s.get("E77"), 374600, 3000),
        "Topf30k D83 Quote": (s.get("D83"), 0.1773, 0.001),
        "Topf30k E83 VK": (s.get("E83"), 430500, 3000),
        "Topf50k D87 Quote": (s.get("D87"), 0.1061, 0.001),
        "Topf50k E87 VK": (s.get("E87"), 467800, 3000),
    }

    print(f"{'Kennzahl':<22} {'Ist':>12} {'Soll':>12} {'OK':>4}")
    all_ok = True
    for name, (ist, soll, tol) in results.items():
        ist_v = ist if isinstance(ist, (int, float)) else float("nan")
        ok = isinstance(ist, (int, float)) and approx(ist_v, soll, tol)
        all_ok = all_ok and ok
        print(f"{name:<22} {ist_v:>12.4f} {soll:>12.4f} {'OK' if ok else 'XX':>4}")

    # I38-Konsistenz: Topf-0-Zeile (E77) muss exakt der aktuellen VK-Summe entsprechen.
    # I18..I37 = (G*(1-C8)*(1-C7)-C11)/C14 ; bei C11=0 Summe = (1-C7)/C14 * (1-C8) * G38
    c8 = s.get("C8"); c7 = s.get("C7"); c14 = s.get("C14"); g38 = s.get("G38")
    i38_manual = (1 - c7) / c14 * (1 - c8) * g38
    e77 = s.get("E77")
    cons = approx(i38_manual, e77, 1)
    all_ok = all_ok and cons
    print(f"\nI38-Konsistenz (E77 == I38): E77={e77:.1f}  I38={i38_manual:.1f}  {'OK' if cons else 'XX'}")

    print("\n=> ALLE CHECKS BESTANDEN" if all_ok else "\n=> FEHLER: Abweichung gefunden")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
