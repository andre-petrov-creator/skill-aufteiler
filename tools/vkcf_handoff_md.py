#!/usr/bin/env python3
"""Erzeugt die Zell-Vertragstabelle des Reiters "Verkauf Cashflow" als Markdown aus tools/vkcf_vertrag.py.

Lauf:   python tools/vkcf_handoff_md.py [--out docs/excel_handoff_vkcf.md]

Die Tabelle ist generiert, nicht handgepflegt (Vault: Spaltenvertrag ist die einzige Quelle) und wird in
docs/excel_handoff.md und in der Spec (Anhang A) per Verweis eingebunden.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vkcf_vertrag as V  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def md_escape(s: str | None) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO_ROOT / "docs" / "excel_handoff_vkcf.md"))
    args = ap.parse_args()
    vt = V.vertrag()
    L = V.LAYOUT
    lines = [
        "# Zell-Vertrag `Verkauf Cashflow` — Vorwärtskalkulation je Wohnung (generiert)",
        "",
        f"Generiert aus `tools/vkcf_vertrag.py` (+ `vkcf_vertrag_daten.py`, `vkcf_vertrag_hand.py`) — {len(vt)} Spalten, "
        f"Blockzeile {L.block_row}, Kopfzeile {L.header_row}, Datenzeilen {L.first}–{L.last}, Summenzeile {L.sum_row}, "
        f"Parameterblock ab Zeile {L.param_title_row}. Marker `{V.VERSION_MARKER}` / `{V.LAYOUT_MARKER}` = {V.LAYOUT_VERSION}. "
        "Nicht von Hand ändern — `python tools/vkcf_handoff_md.py`.",
        "",
        "Formeln sind mit Platzhaltern notiert (`{key}` = eigene Zeile, `{key$}` spaltenabsolut, `{key@sum}` Summenzeile, "
        "`{p:key}` Parameter (immer absolut), `{MIETER!F}` Fremdblatt mit Zeilenoffset); Adressen vergibt die Migration aus dem Layout.",
        "",
        "## Parameterblock (unter der Tabelle)",
        "",
        "| Schlüssel | Zelle | Gruppe | Bezeichnung | Wert / Formel | Format | Eingabe |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in V.PARAMETER:
        wf = f"`={md_escape(p.formel)}`" if p.formel else (md_escape(str(p.wert)) if p.wert is not None else "_leer (Eingabe)_")
        lines.append(f"| `{p.key}` | `{vt.param_cell(p.key)}` | {p.gruppe} | {md_escape(p.label)} | {wf} | `{md_escape(p.format)}` | {'ja' if p.eingabe else '–'} |")
    lines += ["", "## Datenblock (eine Zeile = eine Wohnung)", ""]
    block = None
    for sp in vt.spalten:
        if sp.block != block:
            block = sp.block
            lines += ["", f"### Block {block}", "", f"| Sp. | Schlüssel | Kopf | Typ | Formel (Zeile {L.first}) / Eingabe | Summe ({L.sum_row}) | Format | CRM-Feld | Gruppe |", "|---|---|---|---|---|---|---|---|---|"]
        if sp.typ == "formel":
            f = f"`={md_escape(sp.formel)}`"
        elif sp.typ == "konstante":
            f = "laufende Nr. 1–20"
        else:
            f = md_escape(sp.kommentar) or "_Eingabe_"
        s = f"`={md_escape(sp.summe)}`" if sp.summe else ("`SUMME / Ø`" if sp.typ == "konstante" else "–")
        lines.append(f"| **{vt.letter[sp.schluessel]}** | `{sp.schluessel}` | {md_escape(sp.kopf)} | {sp.typ} | {f} | {s} | `{md_escape(sp.format)}` | {md_escape(sp.crm_feld)} | {'eingeklappt' if sp.gruppiert else ''} |")
    lines[lines.index("## Datenblock (eine Zeile = eine Wohnung)")] = f"## Datenblock (eine Zeile = eine Wohnung, Zeilen {L.first}–{L.last}; Formeln für Zeile {L.first})"
    lines += ["", "## Mitzieher (Zellen außerhalb des Datenblocks)", "", "| Blatt | Zelle(n) | Formel | Warum |", "|---|---|---|---|"]
    seen = {}
    for m in V.MITZIEHER:
        key = (m.sheet, m.formel, m.warum)
        seen.setdefault(key, []).append(m.zelle)
    for (sheet, formel, warum), zellen in seen.items():
        rng = f"{zellen[0]}…{zellen[-1]}" if len(zellen) > 1 else zellen[0]
        lines.append(f"| `{sheet}` | `{rng}` ({len(zellen)}) | `={md_escape(formel)}` | {md_escape(warum)} |")
    lines += ["", "## Gruppierung, Formatierung, Prüfung", "",
              f"- Fixierung rechts von `{V.FREEZE_AFTER_KEY}` (Spalte {vt.letter[V.FREEZE_AFTER_KEY]}) und der Kopfzeilen 1–{L.header_row}.",
              "- Eingeklappte Hilfsspalten (Outline-Ebene 1): " + ", ".join(f"{vt.letter[a]}" + (f":{vt.letter[b]}" if a != b else "") for a, b in V.GRUPPEN) + ".",
              f"- {len(V.CF_REGELN)} Regeln bedingter Formatierung (grün = aktiver Eingabe-Weg, grau = wirkt im gewählten Weg nicht, "
              "orange = Rückfall auf den Regler / Miete angehoben, rot = Datenfehler); Eingabefelder statisch "
              f"`{V.FARBE_EINGABE}`. {len(V.DV_REGELN)} Datenprüfungen (alle `allow_blank`).",
              f"- Legende links unten ab Zeile {V.LEGENDE_FIRST_ROW}: " + " · ".join(f"{e.stichwort} = {md_escape(e.text)}" for e in V.LEGENDE) + ".",
              "- Eingabe-Weg (`eingabe_modus`): 1 = Regler €/m², 2 = Ziel-Bruttomietrendite, 3 = Ziel-Cashflow nach Steuern mit Subvention; "
              "Preis aus `kaufpreis_ziel`, Zeilen ohne Miete fallen auf den Regler zurück (`preis_quelle`).",
              "- Abnahme: `python tools/verify_vkcf_vorwaertskalkulation.py --file <xlsx> --source <original> --calc` "
              "(Vertrag Zelle für Zelle mit Rücksubstitution Buchstabe→Schlüssel, Roundtrip gegen das Original, Rechenabnahme mit `formulas` gegen `tools/fixtures/vkcf_referenz.json`).",
              ""]
    out = Path(args.out)
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"geschrieben: {out} ({len(lines)} Zeilen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
