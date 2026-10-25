"""CHECK24 PriceHugger CLI-Wrapper.

Befüllt das CHECK24-Bewertungsformular mit einem GENERALISIERTEN Datensatz
(Durchschnitts-WE statt Einzel-Wohnung) und gibt Min/Max/Mittel-Marktwert
als JSON zurück.

CLI nimmt entweder Einzel-WE-Listen ODER Gesamt-Summen:

    python tools/m00_check24_pricer.py \
      --strasse "Prosperstr." --hausnr 59 --plz 45356 --ort Essen \
      --baujahr 1977 --zustand gut --ausstattung normal \
      --anzahl-we 6 \
      --wohnflaechen-qm 60,70,80,85,90,95 \
      --zimmer-liste 2,3,3,3,4,4 \
      --anzahl-garagen 4 --anzahl-aussenstellplaetze 2

ODER:

    python tools/m00_check24_pricer.py \
      --strasse "Prosperstr." --hausnr 59 --plz 45356 --ort Essen \
      --baujahr 1977 --zustand gut --ausstattung normal \
      --anzahl-we 6 \
      --gesamtwohnflaeche-qm 480 --gesamtzimmer 19

Exit-Codes: 0 bei status=ok, 1 bei status=error.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
elif not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from check24.form_steps import RunConfig, run  # noqa: E402
from check24.generalisierter_datensatz import (  # noqa: E402
    AUSSTATTUNG_VALUES,
    ZUSTAND_VALUES,
    from_lists,
    from_summary,
)


def _csv_floats(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CHECK24 PriceHugger Marktwert-Scraper")

    p.add_argument("--strasse", required=True)
    p.add_argument("--hausnr", required=True)
    p.add_argument("--plz", required=True)
    p.add_argument("--ort", required=True)
    p.add_argument("--baujahr", type=int, required=True)
    p.add_argument("--zustand", choices=ZUSTAND_VALUES, required=True)
    p.add_argument("--ausstattung", choices=AUSSTATTUNG_VALUES, required=True)

    p.add_argument("--anzahl-we", type=int, required=True)

    p.add_argument("--wohnflaechen-qm", type=_csv_floats, help="Liste, z.B. '60,70,80,85,90,95'")
    p.add_argument("--zimmer-liste", type=_csv_floats, help="Liste, z.B. '2,3,3,3,4,4'")
    p.add_argument("--badezimmer-liste", type=_csv_floats)

    p.add_argument("--gesamtwohnflaeche-qm", type=float)
    p.add_argument("--gesamtzimmer", type=float)

    p.add_argument("--anzahl-garagen", type=int, default=0)
    p.add_argument("--anzahl-aussenstellplaetze", type=int, default=0)

    p.add_argument("--kaufabsicht", choices=("kauf", "verkauf"), default="kauf")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--verbose", action="store_true", help="Diagnose-Logs auf stderr")
    return p.parse_args(argv)


def _build_datensatz(args: argparse.Namespace):
    common = dict(
        strasse=args.strasse,
        hausnr=args.hausnr,
        plz=args.plz,
        ort=args.ort,
        baujahr=args.baujahr,
        zustand=args.zustand,
        ausstattung=args.ausstattung,
        anzahl_garagen=args.anzahl_garagen,
        anzahl_aussenstellplaetze=args.anzahl_aussenstellplaetze,
    )

    if args.wohnflaechen_qm and args.zimmer_liste:
        if len(args.wohnflaechen_qm) != args.anzahl_we:
            raise SystemExit(
                f"Listen-Länge ({len(args.wohnflaechen_qm)}) passt nicht zu --anzahl-we ({args.anzahl_we})"
            )
        badeliste = [int(b) for b in args.badezimmer_liste] if args.badezimmer_liste else None
        return from_lists(
            wohnflaechen_qm=args.wohnflaechen_qm,
            zimmer_liste=args.zimmer_liste,
            badezimmer_liste=badeliste,
            **common,
        )

    if args.gesamtwohnflaeche_qm is None or args.gesamtzimmer is None:
        raise SystemExit(
            "Entweder --wohnflaechen-qm+--zimmer-liste ODER --gesamtwohnflaeche-qm+--gesamtzimmer angeben."
        )

    return from_summary(
        anzahl_we=args.anzahl_we,
        gesamtwohnflaeche_qm=args.gesamtwohnflaeche_qm,
        gesamtzimmer=args.gesamtzimmer,
        **common,
    )


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    d = _build_datensatz(args)
    cfg = RunConfig(headless=args.headless, kaufabsicht=args.kaufabsicht, verbose=args.verbose)

    result = run(d, cfg)
    result["generalisierter_datensatz"] = asdict(d)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
