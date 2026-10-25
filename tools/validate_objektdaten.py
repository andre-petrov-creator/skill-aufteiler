"""Aufteiler objektdaten.json Validator (Refactor v2.0).

Lauf: python tools/validate_objektdaten.py <pfad-zu-objektdaten.json>
Returncode 0 = valid, 1 = invalid (Fehler auf stderr), 2 = Usage/IO-Fehler.

Prüft die generalisierte Datenbasis gegen das Schema aus docs/objektdaten-schema.md.
Kein JSON-Schema-File — Regeln sind hier deklarativ als Code (Schema ist Markdown,
nicht JSON-Schema). Reicht aus für die Phase-4-Tests; bei Bedarf später extrahieren.

Geprüft wird:
  1. Top-Level-Struktur (Pflicht-Blöcke vorhanden)
  2. Pflicht-Felder gefüllt + annotiert (wert/quelle/zitat/konfidenz)
  3. WE-Liste-Konsistenz (Länge == anzahl_we, Σ Wfl ≈ Gesamt-Wfl ±2%)
  4. Modernisierung-Bestand vollständig (alle 8 Gewerke vorhanden, jahr darf null sein)
  5. Konfidenz-Werte ∈ {hoch, mittel, niedrig}
  6. Scoring-Block vollständig (5 Sub-Scores + Gesamt, alle 0-10)
  7. Ampel-Penalty: ≥2 rote Sub-Scores → Gesamt-Ampel "rot"
"""
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL = [
    "schema_version", "objekt_slug", "erstellt_am",
    "quellen", "adresse", "objekt", "we_liste",
    "preise", "modernisierung_bestand",
]

PFLICHT_ADRESSE = ["strasse", "hausnummer", "plz", "ort", "bundesland", "adresse_volltext"]
PFLICHT_OBJEKT  = ["objekttyp", "baujahr", "wohnflaeche_gesamt_qm", "grundstueck_qm", "anzahl_we"]
PFLICHT_PREISE  = ["angebotspreis_eur", "kaufpreis_eur_pro_qm", "kaufnebenkosten_prozent"]

PFLICHT_WE_FELDER = ["we_nr", "etage", "wohnflaeche_qm", "zimmer_anzahl", "leer"]

GEWERKE_PFLICHT = [
    "dach", "fassade", "fenster", "leitungen",
    "heizung", "baeder", "innenausbau", "grundriss",
]

KONFIDENZ_WERTE = {"hoch", "mittel", "niedrig"}
AMPEL_WERTE     = {"gruen", "gelb", "rot"}
AMPEL_NV_WERTE  = AMPEL_WERTE | {"nv"}            # nur für Achse 5 (aufteilungs_premium_plz)

SUBSCORES_PFLICHT = ["lage", "miet_potenzial", "energie", "zustand", "deal"]

# markt.stadtteil_vergleich (seit v3.2, 5. Achse seit v3.3)
STADTTEIL_VERGLEICH_ACHSEN_4 = [
    "verkaufspreis_eur_pro_qm",
    "mietpreis_eur_pro_qm_mo",
    "vermarktungsdauer_verkauf_tage",
    "vermarktungsdauer_miete_tage",
]
STADTTEIL_VERGLEICH_ACHSE_5 = "aufteilungs_premium_plz"
CAVEAT_WERTE = {
    "tool_quirk_mfh_eq_etw",
    "tool_quirk_miete_leck",
    "zu_wenig_inserate",
}


def _is_annotated(node: Any) -> bool:
    """Ein Feld ist annotiert wenn es dict mit 'wert' ist."""
    return isinstance(node, dict) and "wert" in node


def _check_annotation(path: str, node: Any, errors: list[str]) -> None:
    """Prüft dass annotierter Eintrag wert/quelle/zitat/konfidenz hat."""
    if not _is_annotated(node):
        errors.append(f"{path}: erwartetes annotiertes Feld, ist {type(node).__name__}")
        return
    for k in ("wert", "quelle", "zitat", "konfidenz"):
        if k not in node:
            errors.append(f"{path}: fehlt '{k}' in Annotation")
    konf = node.get("konfidenz")
    if konf is not None and konf not in KONFIDENZ_WERTE:
        errors.append(f"{path}.konfidenz: '{konf}' nicht in {KONFIDENZ_WERTE}")


def _check_top_level(data: dict, errors: list[str]) -> None:
    for k in REQUIRED_TOP_LEVEL:
        if k not in data:
            errors.append(f"Top-Level: fehlt '{k}'")
    if data.get("schema_version") != "2.0":
        errors.append(f"schema_version: erwartet '2.0', ist '{data.get('schema_version')}'")


def _check_adresse(data: dict, errors: list[str]) -> None:
    adr = data.get("adresse", {})
    for k in PFLICHT_ADRESSE:
        if k not in adr:
            errors.append(f"adresse: fehlt '{k}'")
            continue
        _check_annotation(f"adresse.{k}", adr[k], errors)


def _check_objekt(data: dict, errors: list[str]) -> None:
    obj = data.get("objekt", {})
    for k in PFLICHT_OBJEKT:
        if k not in obj:
            errors.append(f"objekt: fehlt '{k}'")
            continue
        _check_annotation(f"objekt.{k}", obj[k], errors)
    bj = obj.get("baujahr", {}).get("wert")
    if isinstance(bj, int) and not (1850 <= bj <= 2030):
        errors.append(f"objekt.baujahr.wert: {bj} außerhalb Plausi 1850-2030")
    n = obj.get("anzahl_we", {}).get("wert")
    if isinstance(n, int) and n < 1:
        errors.append(f"objekt.anzahl_we.wert: {n} muss ≥ 1 sein")


def _check_we_liste(data: dict, errors: list[str]) -> None:
    we_liste = data.get("we_liste", [])
    if not isinstance(we_liste, list):
        errors.append("we_liste: kein Array")
        return
    n_erwartet = data.get("objekt", {}).get("anzahl_we", {}).get("wert")
    if isinstance(n_erwartet, int) and len(we_liste) != n_erwartet:
        errors.append(f"we_liste: Länge {len(we_liste)} != objekt.anzahl_we.wert {n_erwartet}")

    summe_wfl = 0.0
    for i, we in enumerate(we_liste):
        if not isinstance(we, dict):
            errors.append(f"we_liste[{i}]: kein Objekt")
            continue
        for k in PFLICHT_WE_FELDER:
            if k not in we:
                errors.append(f"we_liste[{i}]: fehlt '{k}'")
                continue
            if k == "we_nr":
                if not isinstance(we[k], int):
                    errors.append(f"we_liste[{i}].we_nr: kein int")
            else:
                _check_annotation(f"we_liste[{i}].{k}", we[k], errors)
        wfl = (we.get("wohnflaeche_qm") or {}).get("wert")
        if isinstance(wfl, (int, float)):
            summe_wfl += wfl
        leer = (we.get("leer") or {}).get("wert")
        if leer is False and "ist_miete_eur_monat" not in we:
            errors.append(f"we_liste[{i}]: leer=false aber 'ist_miete_eur_monat' fehlt")

    gesamt_wfl = data.get("objekt", {}).get("wohnflaeche_gesamt_qm", {}).get("wert")
    if isinstance(gesamt_wfl, (int, float)) and gesamt_wfl > 0:
        abw = abs(summe_wfl - gesamt_wfl) / gesamt_wfl
        if abw > 0.02:
            errors.append(
                f"we_liste: Σ Wohnfläche {summe_wfl:.2f} weicht von "
                f"objekt.wohnflaeche_gesamt_qm {gesamt_wfl:.2f} um {abw*100:.1f}% ab (max 2%)"
            )


def _check_preise(data: dict, errors: list[str]) -> None:
    pr = data.get("preise", {})
    for k in PFLICHT_PREISE:
        if k not in pr:
            errors.append(f"preise: fehlt '{k}'")
            continue
        _check_annotation(f"preise.{k}", pr[k], errors)


def _check_modernisierung(data: dict, errors: list[str]) -> None:
    mb = data.get("modernisierung_bestand", {})
    for g in GEWERKE_PFLICHT:
        if g not in mb:
            errors.append(f"modernisierung_bestand: fehlt Gewerk '{g}' (jahr darf null sein, Feld muss da sein)")
            continue
        entry = mb[g]
        if not isinstance(entry, dict):
            errors.append(f"modernisierung_bestand.{g}: kein Objekt")
            continue
        if "jahr" not in entry:
            errors.append(f"modernisierung_bestand.{g}: fehlt 'jahr' (darf null sein)")


def _check_freitext_befunde(data: dict, errors: list[str]) -> None:
    """freitext_befunde[] muss vorhanden sein. Wenn leer: Begründung in meta.coverage_check."""
    fb = data.get("freitext_befunde")
    if fb is None:
        errors.append("freitext_befunde: Block fehlt komplett (muss Array sein, ggf. leer mit Begründung)")
        return
    if not isinstance(fb, list):
        errors.append("freitext_befunde: kein Array")
        return

    if len(fb) == 0:
        cc = (data.get("meta") or {}).get("coverage_check") or {}
        if not cc.get("no_freitext_befunde_begruendung"):
            errors.append(
                "freitext_befunde[]: leer aber keine Begründung in "
                "meta.coverage_check.no_freitext_befunde_begruendung"
            )

    for i, entry in enumerate(fb):
        if not isinstance(entry, dict):
            errors.append(f"freitext_befunde[{i}]: kein Objekt")
            continue
        for k in ("thema", "befund", "quelle", "zitat", "relevanz"):
            if k not in entry:
                errors.append(f"freitext_befunde[{i}]: fehlt '{k}'")
        rel = entry.get("relevanz")
        if rel not in ("hoch", "mittel", "niedrig"):
            errors.append(f"freitext_befunde[{i}].relevanz: '{rel}' nicht in {{hoch,mittel,niedrig}}")


def _check_coverage(data: dict, errors: list[str]) -> None:
    """meta.coverage_check Pflicht-Felder."""
    meta = data.get("meta")
    if meta is None:
        errors.append("meta: Block fehlt")
        return
    cc = meta.get("coverage_check")
    if cc is None:
        errors.append("meta.coverage_check: Block fehlt")
        return
    if not cc.get("second_pass_durchgeführt"):
        errors.append("meta.coverage_check.second_pass_durchgeführt: muss true sein")
    sz = cc.get("stichproben_zitate") or []
    if not isinstance(sz, list):
        errors.append("meta.coverage_check.stichproben_zitate: kein Array")
    elif len(sz) < 5:
        errors.append(
            f"meta.coverage_check.stichproben_zitate: nur {len(sz)} Einträge (min 5 erforderlich)"
        )
    else:
        for i, e in enumerate(sz):
            if not isinstance(e, dict):
                errors.append(f"meta.coverage_check.stichproben_zitate[{i}]: kein Objekt")
                continue
            for k in ("zitat", "quelle", "extrahiert_nach"):
                if k not in e:
                    errors.append(f"meta.coverage_check.stichproben_zitate[{i}]: fehlt '{k}'")


def _check_scoring(data: dict, errors: list[str]) -> None:
    sc = data.get("scoring")
    if sc is None:
        errors.append("scoring: Block fehlt komplett")
        return
    subs = sc.get("subscores", {})
    rote_count = 0
    for k in SUBSCORES_PFLICHT:
        if k not in subs:
            errors.append(f"scoring.subscores: fehlt '{k}'")
            continue
        s = subs[k]
        wert = s.get("wert")
        ampel = s.get("ampel")
        if not isinstance(wert, (int, float)) or not (0 <= wert <= 10):
            errors.append(f"scoring.subscores.{k}.wert: '{wert}' nicht in [0, 10]")
        if ampel not in AMPEL_WERTE:
            errors.append(f"scoring.subscores.{k}.ampel: '{ampel}' nicht in {AMPEL_WERTE}")
        if ampel == "rot":
            rote_count += 1

    ges = sc.get("gesamt", {})
    gw = ges.get("wert")
    ga = ges.get("ampel")
    if not isinstance(gw, (int, float)) or not (0 <= gw <= 10):
        errors.append(f"scoring.gesamt.wert: '{gw}' nicht in [0, 10]")
    if ga not in AMPEL_WERTE:
        errors.append(f"scoring.gesamt.ampel: '{ga}' nicht in {AMPEL_WERTE}")

    if rote_count >= 2 and ga != "rot":
        errors.append(
            f"scoring.gesamt.ampel: {rote_count} rote Sub-Scores → "
            f"Gesamt-Ampel muss 'rot' sein, ist '{ga}'"
        )


def _check_markt_stadtteil_vergleich(data: dict, errors: list[str]) -> None:
    """Validiert markt.stadtteil_vergleich (5-Achsen-Markt-Indikator, seit v3.2 / 5. Achse seit v3.3).

    Soft-Skip: Block ist optional auf Top-Level (`markt` kann fehlen, oder `stadtteil_vergleich`
    in `markt` kann fehlen). Wenn vorhanden, dann:
      - Achsen 1–4 müssen ampel ∈ {gruen, gelb, rot} haben
      - Achse 5 (aufteilungs_premium_plz) darf zusätzlich ampel='nv' haben
        und MUSS dann caveat ∈ CAVEAT_WERTE haben (Konsistenz-Regel)
      - verdikt.ampel ∈ {gruen, gelb, rot}, verdikt.anzahl_achsen == 5
    """
    markt = data.get("markt")
    if not isinstance(markt, dict):
        return  # markt-Block optional — kein Fehler
    sv = markt.get("stadtteil_vergleich")
    if sv is None:
        return  # stadtteil_vergleich optional
    if not isinstance(sv, dict):
        errors.append("markt.stadtteil_vergleich: kein Objekt")
        return

    # Achsen 1–4: nur gruen/gelb/rot
    for achse in STADTTEIL_VERGLEICH_ACHSEN_4:
        if achse not in sv:
            errors.append(f"markt.stadtteil_vergleich: fehlt Achse '{achse}'")
            continue
        a = sv[achse]
        if not isinstance(a, dict):
            errors.append(f"markt.stadtteil_vergleich.{achse}: kein Objekt")
            continue
        ampel = a.get("ampel")
        if ampel not in AMPEL_WERTE:
            errors.append(
                f"markt.stadtteil_vergleich.{achse}.ampel: '{ampel}' nicht in {AMPEL_WERTE}"
            )

    # Achse 5: gruen/gelb/rot/nv + caveat-Konsistenz
    if STADTTEIL_VERGLEICH_ACHSE_5 not in sv:
        errors.append(f"markt.stadtteil_vergleich: fehlt Achse '{STADTTEIL_VERGLEICH_ACHSE_5}'")
    else:
        a5 = sv[STADTTEIL_VERGLEICH_ACHSE_5]
        if not isinstance(a5, dict):
            errors.append(f"markt.stadtteil_vergleich.{STADTTEIL_VERGLEICH_ACHSE_5}: kein Objekt")
        else:
            ampel = a5.get("ampel")
            caveat = a5.get("caveat")
            if ampel not in AMPEL_NV_WERTE:
                errors.append(
                    f"markt.stadtteil_vergleich.{STADTTEIL_VERGLEICH_ACHSE_5}.ampel: "
                    f"'{ampel}' nicht in {AMPEL_NV_WERTE}"
                )
            if caveat is not None and caveat not in CAVEAT_WERTE:
                errors.append(
                    f"markt.stadtteil_vergleich.{STADTTEIL_VERGLEICH_ACHSE_5}.caveat: "
                    f"'{caveat}' nicht in {CAVEAT_WERTE | {None}}"
                )
            # Konsistenz: caveat != null ⇔ ampel == 'nv'
            if caveat is not None and ampel != "nv":
                errors.append(
                    f"markt.stadtteil_vergleich.{STADTTEIL_VERGLEICH_ACHSE_5}: "
                    f"caveat='{caveat}' erfordert ampel='nv' (ist '{ampel}')"
                )
            if caveat is None and ampel == "nv":
                errors.append(
                    f"markt.stadtteil_vergleich.{STADTTEIL_VERGLEICH_ACHSE_5}: "
                    f"ampel='nv' erfordert nicht-null caveat (ist null)"
                )

    # verdikt-Block
    verdikt = sv.get("verdikt")
    if verdikt is None:
        errors.append("markt.stadtteil_vergleich.verdikt: Block fehlt")
    elif not isinstance(verdikt, dict):
        errors.append("markt.stadtteil_vergleich.verdikt: kein Objekt")
    else:
        ges_ampel = verdikt.get("ampel")
        if ges_ampel not in AMPEL_WERTE:
            errors.append(
                f"markt.stadtteil_vergleich.verdikt.ampel: '{ges_ampel}' nicht in {AMPEL_WERTE}"
            )
        na = verdikt.get("anzahl_achsen")
        if na != 5:
            errors.append(
                f"markt.stadtteil_vergleich.verdikt.anzahl_achsen: {na} != 5"
            )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_objektdaten.py <objektdaten.json>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    if not path.is_file():
        print(f"Datei nicht gefunden: {path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"JSON-Parse-Fehler: {e}", file=sys.stderr)
        return 1

    errors: list[str] = []
    _check_top_level(data, errors)
    _check_adresse(data, errors)
    _check_objekt(data, errors)
    _check_we_liste(data, errors)
    _check_preise(data, errors)
    _check_modernisierung(data, errors)
    _check_freitext_befunde(data, errors)
    _check_coverage(data, errors)
    _check_scoring(data, errors)
    _check_markt_stadtteil_vergleich(data, errors)

    if errors:
        print(f"objektdaten.json INVALID — {len(errors)} Fehler:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"objektdaten.json OK ({path})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
