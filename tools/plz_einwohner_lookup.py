"""PLZ + Stadt-Einwohner-Lookup aus lokalem CSV-Cache.

Datenquelle: WebSearch (Wikipedia für Städte, suche-postleitzahl.org für PLZ).
Pro Lead 1× manuell befüllt — Cache wächst über Zeit dicht.

Usage:
    python tools/plz_einwohner_lookup.py 59494 Soest

Exit-Codes:
    0: PLZ + Stadt im Cache, JSON auf stdout
    1: Argument-Fehler
    2: Cache-Miss (PLZ oder Stadt fehlt) — JSON mit fehlende_eintraege auf stdout
"""

import csv
import json
import os
import sys
from typing import Optional

CACHE_PATH = os.path.join(os.path.dirname(__file__), "plz-einwohner.csv")


def read_cache() -> list[dict]:
    if not os.path.exists(CACHE_PATH):
        return []
    with open(CACHE_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_plz(rows: list[dict], plz: str) -> Optional[dict]:
    for r in rows:
        if r.get("entity_type") == "plz" and r.get("plz") == plz:
            return r
    return None


def find_stadt(rows: list[dict], stadt: str) -> Optional[dict]:
    s = stadt.strip().lower()
    for r in rows:
        if r.get("entity_type") == "stadt" and r.get("stadt", "").strip().lower() == s:
            return r
    return None


def row_to_block(r: dict) -> dict:
    return {
        "wert": int(r["einwohner"]),
        "quelle": r["quelle"],
        "konfidenz": r["konfidenz"],
        "abgerufen_am": r["abgerufen_am"],
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: plz_einwohner_lookup.py <PLZ> <Stadt>", file=sys.stderr)
        return 1

    plz_arg = sys.argv[1].strip()
    stadt_arg = sys.argv[2].strip()

    rows = read_cache()
    plz_row = find_plz(rows, plz_arg)
    stadt_row = find_stadt(rows, stadt_arg)

    result = {
        "plz_einwohner": row_to_block(plz_row) if plz_row else None,
        "stadt_einwohner": row_to_block(stadt_row) if stadt_row else None,
        "fehlende_eintraege": [],
    }

    if not plz_row:
        result["fehlende_eintraege"].append(f"plz:{plz_arg}")
    if not stadt_row:
        result["fehlende_eintraege"].append(f"stadt:{stadt_arg}")

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["fehlende_eintraege"] else 2


if __name__ == "__main__":
    sys.exit(main())
