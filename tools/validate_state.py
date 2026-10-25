"""Aufteiler state.json Validator (Schema-Version-aware).

Lauf: python tools/validate_state.py <pfad-zu-state.json>
Returncode 0 = valid, 1 = invalid (Fehler auf stderr), 2 = Usage-Fehler.

Schema-Versionen:
- "1.0" (Legacy, vor Modul-Umnummerierung 2026-05-26): docs/state.schema.v1.json,
  Module-Blöcke heißen modul_0..modul_5, Massnahmen liegen in modul_3.
- "2.0" (aktuell, ab Modul-Umnummerierung 2026-05-26): docs/state.schema.json,
  Module-Blöcke heißen modul_1..modul_6 (Modul 0 = Akquise schreibt nicht in
  state.json), Massnahmen liegen in modul_4.

Asset-Trennung-Check (Business-Regel über JSON-Schema hinaus): Keine
'subvention'/'rücklage'/'ruecklage' im Reno-Block. Block-Name variiert
nach Schema-Version (modul_3 in v1, modul_4 in v2).
"""
import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_V1_PATH = REPO_ROOT / "docs" / "state.schema.v1.json"
SCHEMA_V2_PATH = REPO_ROOT / "docs" / "state.schema.json"

FORBIDDEN_IN_MASSNAHME = ("subvention", "rücklage", "ruecklage")

# Schema-Version → (schema-file-path, modul-block-name für Massnahmen)
SCHEMA_BY_VERSION = {
    "1.0": (SCHEMA_V1_PATH, "modul_3"),
    "2.0": (SCHEMA_V2_PATH, "modul_4"),
}


def _asset_trennung_check(state: dict, massnahmen_block: str) -> list[str]:
    errors: list[str] = []
    massnahmen = (state.get(massnahmen_block) or {}).get("massnahmen_liste") or []
    for idx, m in enumerate(massnahmen):
        for field in ("kategorie", "ist_zustand", "geplant"):
            text = str(m.get(field, "")).lower()
            for token in FORBIDDEN_IN_MASSNAHME:
                if token in text:
                    errors.append(
                        f"Asset-Trennung verletzt: {massnahmen_block}.massnahmen_liste[{idx}].{field} "
                        f"enthält '{token}' — gehört nicht in Reno-Block."
                    )
    return errors


def _we_konsistenz_check(state: dict, schema_version: str) -> list[str]:
    """Paar- und Plausibilitaets-Regeln fuer die WE-Felder der Verkaufs-Kalkulation (nur Fassung 2.0)."""
    errors: list[str] = []
    if schema_version != "2.0":
        return errors
    m2 = state.get("modul_2") or {}
    m5 = state.get("modul_5") or {}
    nenner = m2.get("mea_nenner")
    zaehler_summe = 0
    for idx, we in enumerate(m2.get("we_liste") or []):
        z = we.get("mea_zaehler")
        if z is None:
            continue
        zaehler_summe += z
        if nenner is not None and z > nenner:
            errors.append(f"modul_2.we_liste[{idx}].mea_zaehler {z} > mea_nenner {nenner}.")
    if nenner is not None and zaehler_summe > nenner:
        errors.append(f"Summe modul_2.we_liste[].mea_zaehler {zaehler_summe} > mea_nenner {nenner}.")

    # Garagen/Stellplaetze: Anzahl je WE (Modul 5) darf den Objektbestand (Modul 2) nicht uebersteigen;
    # ein Preis je Einheit ohne Bestand ist ein Widerspruch (Export wuerde nichts schreiben, aber der State luegt).
    we_mieten = (state.get("modul_5") or {}).get("we_mieten") or []
    for anz_key, gesamt_key, preis_key in (("garagen_anzahl", "garagen_gesamt", "garage_preis_eur"),
                                            ("stellplaetze_anzahl", "stellplaetze_gesamt", "stellplatz_preis_eur")):
        gesamt = m2.get(gesamt_key)
        summe = sum(int(m.get(anz_key) or 0) for m in we_mieten)
        if gesamt is not None and summe > gesamt:
            errors.append(f"Summe modul_5.we_mieten[].{anz_key} {summe} > modul_2.{gesamt_key} {gesamt}.")
        if m2.get(preis_key) is not None and gesamt == 0:
            errors.append(f"modul_2.{preis_key} gesetzt, aber {gesamt_key} = 0.")
    for idx, m in enumerate(m5.get("we_mieten") or []):
        p = f"modul_5.we_mieten[{idx}]"
        hg = m.get("hausgeld_nicht_umlagefaehig_eur_pro_monat")
        rl = m.get("hausgeld_ruecklage_eur_pro_monat")
        if hg is not None and rl is None:
            errors.append(f"{p}: hausgeld_nicht_umlagefaehig_eur_pro_monat ohne hausgeld_ruecklage_eur_pro_monat (Paar-Pflicht).")
        if hg is not None and rl is not None and rl > hg:
            errors.append(f"{p}: hausgeld_ruecklage_eur_pro_monat {rl} > hausgeld_nicht_umlagefaehig_eur_pro_monat {hg}.")
        if hg is not None and m.get("bewirtschaftungsquote_schaetzung") is not None:
            errors.append(f"{p}: bewirtschaftungsquote_schaetzung UND hausgeld_nicht_umlagefaehig_eur_pro_monat gesetzt - nur eine Quelle.")
        # Nur pruefen, wenn das Feld gesetzt ist: Laeufe vor 2026-09-10 kennen es nicht und bleiben valide
        if "leerstand" in m and m.get("ist_miete_eur_pro_qm", 1) == 0 and not m["leerstand"]:
            errors.append(f"{p}: ist_miete_eur_pro_qm = 0, aber leerstand=false.")
        reach = m.get("reach_time_monate")
        subv = m.get("mietsubvention_eur_pro_monat", 0)
        if reach is not None and (reach == 0) != (subv == 0):
            errors.append(f"{p}: reach_time_monate {reach} passt nicht zu mietsubvention_eur_pro_monat {subv}.")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_state.py <state.json>", file=sys.stderr)
        return 2

    state_path = Path(argv[1])
    if not state_path.is_file():
        print(f"State-Datei nicht gefunden: {state_path}", file=sys.stderr)
        return 2

    state = json.loads(state_path.read_text(encoding="utf-8"))
    schema_version = state.get("schema_version")

    if schema_version not in SCHEMA_BY_VERSION:
        print(
            f"[SCHEMA] schema_version '{schema_version}' nicht unterstützt. "
            f"Erwartet: {sorted(SCHEMA_BY_VERSION)}",
            file=sys.stderr,
        )
        return 1

    schema_path, massnahmen_block = SCHEMA_BY_VERSION[schema_version]
    if not schema_path.is_file():
        print(f"Schema-Datei fehlt: {schema_path}", file=sys.stderr)
        return 2

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(state), key=lambda e: list(e.absolute_path))
    business_errors = _asset_trennung_check(state, massnahmen_block) + _we_konsistenz_check(state, schema_version)

    if not schema_errors and not business_errors:
        return 0

    for err in schema_errors:
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        print(f"[SCHEMA] {path}: {err.message}", file=sys.stderr)
    for msg in business_errors:
        print(f"[BUSINESS] {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
