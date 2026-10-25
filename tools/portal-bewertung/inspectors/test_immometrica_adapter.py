"""Final Live-Test fuer den Immometrica-Adapter (Phase D)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from portals.immometrica.portal import run_immometrica


def main() -> int:
    print(">>> Adapter-Live-Test: PLZ 45357 / Essen / Baujahr 1965 / H1/2026 / headed",
          file=sys.stderr, flush=True)
    result = run_immometrica(
        plz="45357",
        stadt="Essen",
        baujahr=1965,
        year_half="H1/2026",
        headless=False,  # headed fuer Verifikation
    )
    print(">>> RESULT (full JSON):", file=sys.stderr, flush=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f">>> Status: {result.get('status')}", file=sys.stderr, flush=True)
    return 0 if result.get("status") in ("ok", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
