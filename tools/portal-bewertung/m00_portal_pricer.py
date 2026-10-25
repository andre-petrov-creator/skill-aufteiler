"""Portal-Pricer CLI — dispatcht auf Portal-Adapter, gibt strukturiertes JSON.

CLI nimmt Adress-/Objekt-Felder als Argumente ODER lädt einen vorgefertigten
GeneralisierterDatensatz aus einer JSON-Datei (`--datensatz <path>`).

Beispiele:

    python m00_portal_pricer.py --portal check24 \\
      --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen \\
      --baujahr 1965 --zustand gut --ausstattung normal \\
      --anzahl-we 4 --gesamtwohnflaeche-qm 320 --gesamtzimmer 12 \\
      --headless

    python m00_portal_pricer.py --portal check24 \\
      --datensatz runs/datensatz.json --headless

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
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")  # type: ignore[assignment]

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from core.datensatz import (  # noqa: E402
    AUSSTATTUNG_VALUES,
    ZUSTAND_VALUES,
    GeneralisierterDatensatz,
    from_lists,
    from_summary,
)
from core.portal_base import PortalBase, RunConfig  # noqa: E402
from core.runner import run  # noqa: E402

# Portal-Dispatcher: NAME → Klasse. Weitere Portale werden hier registriert.
from portals.check24.portal import Check24Portal  # noqa: E402
from portals.homeday.portal import HomedayPortal  # noqa: E402
from portals.interhyp.portal import InterhypPortal  # noqa: E402

PORTAL_REGISTRY: dict[str, type[PortalBase]] = {
    "check24": Check24Portal,
    "homeday": HomedayPortal,
    "interhyp": InterhypPortal,
}

# Special-Case: Immometrica nutzt nodriver (Anti-Detect), nicht PortalBase.
# Registry-Eintrag nur fuer CLI-Validation; Dispatch erfolgt separat.
IMMOMETRICA_NAME = "immometrica"
PORTAL_CHOICES = sorted(set(list(PORTAL_REGISTRY.keys()) + [IMMOMETRICA_NAME]))


def _csv_floats(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Portal-Pricer — Marktwert-Scraper für deutsche Immobilien-Bewertungsportale."
    )

    p.add_argument(
        "--portal",
        required=False,
        choices=PORTAL_CHOICES,
        help="Welches Portal abrufen (Single-Modus).",
    )
    p.add_argument(
        "--alle",
        action="store_true",
        help="Multi-Modus: ruft ALLE Portale parallel auf via Orchestrator. "
             "Liefert Konsens-Median + Einzelwerte als JSON.",
    )

    # Mode A: Datensatz aus JSON-Datei laden
    p.add_argument(
        "--datensatz",
        type=Path,
        help="Pfad zu einer JSON-Datei mit GeneralisierterDatensatz. Wenn gesetzt, "
        "werden Adress-/Objekt-Argumente ignoriert.",
    )

    # Mode B: Datensatz aus CLI-Args bauen
    p.add_argument("--strasse")
    p.add_argument("--hausnr")
    p.add_argument("--plz")
    p.add_argument("--ort")
    p.add_argument("--baujahr", type=int)
    p.add_argument("--zustand", choices=ZUSTAND_VALUES)
    p.add_argument("--ausstattung", choices=AUSSTATTUNG_VALUES)

    p.add_argument("--anzahl-we", type=int)
    p.add_argument("--wohnflaechen-qm", type=_csv_floats, help="Liste, z.B. '60,70,80'")
    p.add_argument("--zimmer-liste", type=_csv_floats, help="Liste, z.B. '2,3,3'")
    p.add_argument("--badezimmer-liste", type=_csv_floats)
    p.add_argument("--gesamtwohnflaeche-qm", type=float)
    p.add_argument("--gesamtzimmer", type=float)
    p.add_argument("--anzahl-garagen", type=int, default=0)
    p.add_argument("--anzahl-aussenstellplaetze", type=int, default=0)
    p.add_argument("--avg-badezimmer", type=int, default=1)

    # Run-Flags
    p.add_argument(
        "--kaufabsicht",
        choices=("kauf", "verkauf"),
        default="kauf",
        help="Vom Portal interpretiert (CHECK24: Kaufen/Verkaufen-Radio).",
    )
    p.add_argument("--headless", action="store_true", help="Browser im Hintergrund.")
    p.add_argument(
        "--verbose", action="store_true", help="Diagnose-Logs auf stderr."
    )

    return p.parse_args(argv)


def _build_datensatz_from_args(args: argparse.Namespace) -> GeneralisierterDatensatz:
    required = ["strasse", "hausnr", "plz", "ort", "baujahr", "zustand", "ausstattung", "anzahl_we"]
    missing = [r for r in required if getattr(args, r) in (None, "")]
    if missing:
        raise SystemExit(
            f"Fehlende Argumente: {', '.join('--' + m.replace('_', '-') for m in missing)}"
        )

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
                f"Listen-Länge ({len(args.wohnflaechen_qm)}) "
                f"passt nicht zu --anzahl-we ({args.anzahl_we})"
            )
        badeliste = (
            [int(b) for b in args.badezimmer_liste] if args.badezimmer_liste else None
        )
        return from_lists(
            wohnflaechen_qm=args.wohnflaechen_qm,
            zimmer_liste=args.zimmer_liste,
            badezimmer_liste=badeliste,
            **common,
        )

    if args.gesamtwohnflaeche_qm is None or args.gesamtzimmer is None:
        raise SystemExit(
            "Entweder --wohnflaechen-qm + --zimmer-liste ODER "
            "--gesamtwohnflaeche-qm + --gesamtzimmer angeben."
        )

    return from_summary(
        anzahl_we=args.anzahl_we,
        gesamtwohnflaeche_qm=args.gesamtwohnflaeche_qm,
        gesamtzimmer=args.gesamtzimmer,
        avg_badezimmer=args.avg_badezimmer,
        **common,
    )


def _load_datensatz_from_json(path: Path) -> GeneralisierterDatensatz:
    data = json.loads(path.read_text(encoding="utf-8"))
    return GeneralisierterDatensatz(**data)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    if not args.alle and not args.portal:
        print("Fehler: entweder --portal <name> oder --alle erforderlich.",
              file=sys.stderr)
        return 2

    if args.datensatz:
        d = _load_datensatz_from_json(args.datensatz)
    else:
        d = _build_datensatz_from_args(args)

    # Multi-Modus: alle Portale parallel
    if args.alle:
        from orchestrator import run_all_portals  # noqa: E402

        agg = run_all_portals(
            datensatz=d,
            headless=args.headless,
            kaufabsicht=args.kaufabsicht,
            verbose=args.verbose,
        )
        print(json.dumps(agg, ensure_ascii=False, indent=2, default=str))
        return 0 if agg.get("status") in ("ok", "partial") else 1

    # Single-Modus Special-Case: Immometrica via nodriver
    if args.portal == IMMOMETRICA_NAME:
        from portals.immometrica.portal import run_immometrica  # noqa: E402

        out = run_immometrica(
            plz=str(d.plz),
            stadt=str(d.ort),
            baujahr=int(d.baujahr),
            year_half="latest",
            headless=args.headless,
        )
        out["generalisierter_datensatz"] = asdict(d)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("status") in ("ok", "partial") else 1

    portal_cls = PORTAL_REGISTRY[args.portal]
    portal = portal_cls()

    cfg = RunConfig(
        headless=args.headless,
        verbose=args.verbose,
        kaufabsicht=args.kaufabsicht,
    )
    cfg.browser.headless = args.headless

    result = run(portal, d, cfg)
    out = result.to_dict()
    out["generalisierter_datensatz"] = asdict(d)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
