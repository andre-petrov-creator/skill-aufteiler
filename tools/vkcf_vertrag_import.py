#!/usr/bin/env python3
"""Importiert den geprueften Spaltenvertrag (JSON aus der Revisions-Runde) nach tools/vkcf_vertrag_daten.py.

Lauf:   python tools/vkcf_vertrag_import.py <revision.json> [--out tools/vkcf_vertrag_daten.py]

Die JSON-Formeln tragen echte Adressen im Revisions-Layout (Kopf 17, Daten 18-37, Summe 38, Parameter in
C5..C15 / N5..N14). Sie werden per Ruecksubstitution zu Platzhaltern ({key}, {key@sum}, {p:zins}, ...) und
sofort im selben Legacy-Layout zurueckgerendert - der Round-Trip muss die Originalformel exakt reproduzieren.
Damit ist bewiesen, dass jede Adresse genau die Spalte bzw. den Parameter trifft, den der Vertrag meint.
Beim Bau werden die Platzhalter dann im AKTUELLEN Layout (vkcf_vertrag.LAYOUT) aufgeloest.
Handgepflegte Teile (Mitzieher, Labels, Regeln) stehen in tools/vkcf_vertrag_hand.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vkcf_vertrag as V  # noqa: E402

# Zahlenformate: Vertrag schreibt "?" statt Euro-/m2-Zeichen; rotes Minus faellt weg (Andre: augenschonend)
FMT_FIX = {
    '#,##0" ?"': V.FMT_EUR, '#,##0.00" ?"': V.FMT_EUR2, '#,##0" ?/m?"': V.FMT_EUR_QM, '#,##0.00" ?/m?"': V.FMT_EUR2_QM,
    '#,##0.00" ?";[Red]\\-#,##0.00" ?"': V.FMT_EUR2, '#,##0" ?";[Red]\\-#,##0" ?"': V.FMT_EUR,
    '[Red]#,##0" ?/m?";-#,##0" ?/m?"': V.FMT_EUR_QM, '0.0%;[Red]\\-0.0%': V.FMT_PCT1,
}

# Parameter-Gruppen im neuen Layout: Reihenfolge = Reihenfolge im JSON je Gruppe
GRUPPE = {**{c: "kaeufer" for c in ("C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13", "C14", "C15")},
          **{c: "objekt" for c in ("N5", "N6", "N7", "N8", "N9", "N10", "N11", "N12", "N13", "N14")}}
KEY_OF_CELL = {v: k for k, v in V.LEGACY_PARAM_CELLS.items()}
LABEL_ZELLE_FEST = {"C45": "A45", "C62": "A62", "C63": "A63", "C64": "A64", "C65": "A65", "C69": "A69"}


def fmt(s: str) -> str:
    s = s or "General"
    return FMT_FIX.get(s, s.replace('" ?/m?"', '" €/m²"').replace('" ?"', '" €"'))


def typ(s: str) -> str:
    s = s.lower()
    if s.startswith("konst"):
        return "konstante"
    if s.startswith("formel"):
        return "formel"
    return "eingabe"


_LEGACY_ADDR = set(V.LEGACY_PARAM_CELLS.values())


def norm_params(formel: str) -> str:
    """Original fuer den Round-Trip-Vergleich normalisieren: Parameteradressen absolut (C15 -> $C$15, der Renderer
    schreibt Parameter immer absolut, damit sie beim Kopieren nicht wandern) und {rowbase} im Legacy-Layout aufloesen.
    Die Relativitaet von Datenblock-Bezuegen bleibt unangetastet."""
    formel = formel.replace("{rowbase}", str(V.LAYOUT_LEGACY.first - 1))

    def repl(m: re.Match) -> str:
        addr = f"{m.group(2)}{m.group(3)}"
        return f"${m.group(2)}${m.group(3)}" if addr in _LEGACY_ADDR else m.group(0)
    return re.sub(r"(?<![!A-Z])(\$?)([A-Z]{1,3})\$?(\d+)(?![\d(])", repl, formel)


def clean_summe(s: str | None) -> str | None:
    if not s or s.strip() == "-":
        return None
    s = s.strip()
    if s.startswith('"'):
        return None
    s = re.split(r"\s{2,}\(", s)[0].strip()
    return s[1:] if s.startswith("=") else s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--out", default=str(Path(__file__).parent / "vkcf_vertrag_daten.py"))
    args = ap.parse_args()
    v = json.loads(Path(args.json).read_text(encoding="utf-8"))
    sp = v["spalten"]
    letters = [s["spalte"] for s in sp]
    keys = [s["schluessel"] for s in sp]
    # Parameter-Objekte zuerst (fuer die Adress-Rueckabbildung), Formeln folgen unten
    param_objs = []
    for p in v["parameterblock"]:
        zelle = p["zelle"]
        key = KEY_OF_CELL[zelle]
        gruppe = GRUPPE.get(zelle, "fest")
        param_objs.append((key, gruppe, zelle, p))
    parameter_stub = [V.Parameter(key=k, label=p["bezeichnung"], gruppe=g, zelle=z if g == "fest" else None,
                                  label_zelle=LABEL_ZELLE_FEST.get(z) if g == "fest" else None)
                      for k, g, z, p in param_objs]
    legacy = V.Vertrag([V.Spalte(schluessel=k, kopf="", block="", typ="formel") for k in keys], parameter_stub, V.LAYOUT_LEGACY)
    assert list(legacy.letter.values()) == letters, "Buchstaben im Vertrag sind nicht lueckenlos A.."
    breiten = {m.group(1): float(m.group(2)) for m in re.finditer(r"\b([A-Z]{1,3})=(\d+(?:\.\d+)?)", str(v.get("formatierung", {}).get("spaltenbreiten", "")))}
    L = V.LAYOUT_LEGACY

    fehler = []
    spalten_src = []
    for s in sp:
        t = typ(s["typ"])
        formel_ph = None
        if t == "formel":
            raw = s["formel"].strip()
            raw = raw[1:] if raw.startswith("=") else raw
            formel_ph = legacy.ruecksubstitution(raw, L.first)
            back = legacy.render(formel_ph, L.first)[1:]
            if back != norm_params(raw):
                fehler.append(f"{s['spalte']} {s['schluessel']}: Round-Trip weicht ab\n   orig {raw}\n   back {back}\n   ph   {formel_ph}")
        summe_raw = clean_summe(s.get("summenzelle"))
        summe_ph = None
        if summe_raw:
            summe_ph = legacy.ruecksubstitution(summe_raw, None)
            back = legacy.render(summe_ph, L.sum_row)[1:]
            if back != norm_params(summe_raw):
                fehler.append(f"{s['spalte']} {s['schluessel']} SUMME: Round-Trip weicht ab\n   orig {summe_raw}\n   back {back}")
        beschr = s["formel"] if t != "formel" else None
        spalten_src.append(
            "    Spalte(schluessel=%r, kopf=%r, block=%r, typ=%r,\n           formel=%r,\n           summe=%r,\n           format=%r, breite=%r, gruppiert=%r, crm_feld=%r, quelle_state=%r,\n           kommentar=%r),"
            % (s["schluessel"], s["kopf"], s["block"], t, formel_ph, summe_ph, fmt(s.get("zahlenformat")),
               breiten.get(s["spalte"], 11.0), bool(s.get("gruppiert")), s.get("crm_feld", "-"), s.get("quelle_state", "-"), beschr))

    param_src = []
    for key, gruppe, zelle, p in param_objs:
        raw = str(p["wert_oder_formel"]).strip()
        wert, formel_ph = None, None
        if raw.startswith("="):
            formel_ph = legacy.ruecksubstitution(raw[1:], None)
            back = legacy.render(formel_ph, L.sum_row)[1:]
            if back != norm_params(raw[1:]):
                fehler.append(f"Parameter {zelle} ({key}): Round-Trip weicht ab\n   orig {raw[1:]}\n   back {back}\n   ph   {formel_ph}")
        elif raw.startswith("("):
            wert = None
        else:
            try:
                wert = float(raw) if "." in raw else int(raw)
            except ValueError:
                wert = raw
        eingabe = formel_ph is None and (raw.startswith("(") or p.get("neu") or zelle in ("C5", "C6", "C7", "C9", "C10", "C11", "C12", "C62", "C64"))
        param_src.append(
            "    Parameter(key=%r, label=%r, gruppe=%r,\n              wert=%r, formel=%r, format=%r, eingabe=%r,\n              kommentar=%r, zelle=%r, label_zelle=%r),"
            % (key, p["bezeichnung"], gruppe, wert, formel_ph, fmt(p.get("zahlenformat")), bool(eingabe), p.get("quelle"),
               zelle if gruppe == "fest" else None, LABEL_ZELLE_FEST.get(zelle) if gruppe == "fest" else None))

    if fehler:
        print("ROUND-TRIP-FEHLER (%d):" % len(fehler))
        for f in fehler:
            print(" -", f.encode("ascii", "replace").decode())
        return 1

    out = Path(args.out)
    gen = ['"""GENERIERT aus %s durch tools/vkcf_vertrag_import.py - nicht von Hand aendern.' % Path(args.json).name,
           "Handgepflegte Vertragsteile (Mitzieher, Labels, Legende, CF/DV, Gruppen) stehen in tools/vkcf_vertrag_hand.py.\"\"\"",
           "from vkcf_vertrag import Spalte, Parameter  # noqa: F401",
           "from vkcf_vertrag_hand import *  # noqa: F401,F403", "",
           "SPALTEN = [", *spalten_src, "]", "", "PARAMETER = [", *param_src, "]", ""]
    out.write_text("\n".join(gen), encoding="utf-8", newline="\n")
    print("geschrieben: %s | %d Spalten, %d Parameter, Round-Trip fuer alle Formeln exakt" % (out, len(spalten_src), len(param_src)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
