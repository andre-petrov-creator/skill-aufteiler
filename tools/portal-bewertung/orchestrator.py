# -*- coding: utf-8 -*-
"""Orchestrator — ruft alle 4 Portale parallel auf, aggregiert zu Konsens.

Step 15 im Implementierungsplan. Konsumiert von:
- CLI `m00_portal_pricer.py --alle`
- Modul 0 (`aufteiler-modul-0-quickcheck`) — siehe Memory
  [[immometrica-marktstatistik-workflow]]

Architektur:
- 4 Portal-Calls parallel via ThreadPoolExecutor (jeder mit eigenem Browser)
- Aggregation: Konsens-Median ueber alle nicht-Null Marktwerte
- Excel-Mapping (KALKU!I13-I17, Reihenfolge wie im Sheet):
    I13 = Homeday €/m²
    I14 = Immometrica PLZ-ETW €/m²       (ersetzt IS24 Preisatlas)
    I15 = CHECK24 €/m²
    I16 = Interhyp €/m²
    I17 = Grundstuecksmarktbericht €/m²  (ersetzt Wohnungsmarktbericht; aus
          Notion-DB, NICHT vom Orchestrator geliefert -> Modul 0 fuellt nach)

Output-Schema (JSON):
{
    "status": "ok|partial|error",
    "portale": {
        "check24":     {"status": ..., "marktwert_eur_mittel": ..., "eur_per_qm": ..., "trend_ampel": ..., ...},
        "homeday":     {...},
        "interhyp":    {...},
        "immometrica": {... + "extra" mit 6 Configs ...}
    },
    "marktwert": {
        "konsens_median_eur": <int>,
        "konsens_spread_eur": <int>,
        "konsens_spread_prozent": <float>,
        "anzahl_quellen": <int>,
        "label": "<menschenlesbar>"
    },
    "eur_per_qm": {
        "homeday":                 <float|null>,
        "immometrica":             <float|null>,    (PLZ-ETW, ersetzt IS24)
        "check24":                 <float|null>,
        "interhyp":                <float|null>,
        "grundstuecksmarktbericht": <float|null>,    (Modul 0 fuellt aus Notion)
        "median":                  <float|null>
    },
    "errors": [<list of error-msgs from failed portals>]
}
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from core.datensatz import GeneralisierterDatensatz
from core.portal_base import RunConfig
from core.runner import run as run_portal
from portals.check24.portal import Check24Portal
from portals.homeday.portal import HomedayPortal
from portals.interhyp.portal import InterhypPortal


_PORTAL_BASE_CLASSES = {
    "check24": Check24Portal,
    "homeday": HomedayPortal,
    "interhyp": InterhypPortal,
}


def _run_portalbase(name: str, datensatz: GeneralisierterDatensatz,
                    headless: bool, kaufabsicht: str, verbose: bool) -> dict:
    """Wrapper fuer PortalBase-basierte Adapter (CHECK24/Homeday/Interhyp)."""
    portal_cls = _PORTAL_BASE_CLASSES[name]
    cfg = RunConfig(headless=headless, verbose=verbose, kaufabsicht=kaufabsicht)
    cfg.browser.headless = headless
    try:
        result = run_portal(portal_cls(), datensatz, cfg)
        out = result.to_dict()
        return out
    except Exception as e:
        return {
            "status": "error",
            "portal": name,
            "error_code": "exception",
            "error_message": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }


def _run_immometrica_wrap(datensatz: GeneralisierterDatensatz, headless: bool) -> dict:
    """Wrapper fuer Immometrica via Subprocess.

    nodriver basiert auf asyncio mit globalem Event-Loop. Bei Aufruf in einem
    ThreadPoolExecutor kollidiert das mit dem Main-Thread und produziert
    'cannot call get() concurrently' Errors nach Browser-Stop, die endlos
    in stderr geloggt werden (Live-Test 2026-05-19: 2.3 GB Log).

    Loesung: Immometrica in eigenem Python-Subprozess starten via
    `m00_portal_pricer.py --portal immometrica`. JSON aus stdout parsen.
    """
    here = Path(__file__).resolve().parent
    venv_py = here / ".venv" / "Scripts" / "python.exe"
    python_exe = str(venv_py) if venv_py.exists() else sys.executable

    cli = here / "m00_portal_pricer.py"

    # Datensatz als JSON-Tempfile (CLI nutzt --datensatz)
    tmpdir = tempfile.mkdtemp(prefix="immo_orchestrator_")
    datensatz_path = Path(tmpdir) / "datensatz.json"
    datensatz_path.write_text(
        json.dumps(asdict(datensatz), ensure_ascii=False),
        encoding="utf-8",
    )

    cmd = [
        python_exe, str(cli),
        "--portal", "immometrica",
        "--datensatz", str(datensatz_path),
    ]
    if headless:
        cmd.append("--headless")

    try:
        # Subprocess mit Timeout 20min - Immometrica kann lange dauern
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1200,
            cwd=str(here),
        )
        if proc.returncode != 0 and not proc.stdout.strip():
            return {
                "status": "error",
                "portal": "immometrica",
                "error_code": "subprocess_failed",
                "error_message": f"exit {proc.returncode}",
                "stderr_tail": (proc.stderr or "")[-2000:],
            }
        # JSON aus stdout extrahieren (CLI gibt eingerueckten Block)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            # Manchmal printtet die CLI andere Zeilen vor dem JSON
            for start in range(len(proc.stdout)):
                if proc.stdout[start] == "{":
                    try:
                        return json.loads(proc.stdout[start:])
                    except Exception:
                        continue
            return {
                "status": "error",
                "portal": "immometrica",
                "error_code": "json_parse_failed",
                "error_message": "Subprocess stdout nicht als JSON parsbar",
                "stdout_head": proc.stdout[:500],
                "stderr_tail": (proc.stderr or "")[-2000:],
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "portal": "immometrica",
            "error_code": "subprocess_timeout",
            "error_message": "Subprocess timeout nach 1200s",
        }
    except Exception as e:
        return {
            "status": "error",
            "portal": "immometrica",
            "error_code": "exception",
            "error_message": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }
    finally:
        try:
            datensatz_path.unlink(missing_ok=True)
            os.rmdir(tmpdir)
        except Exception:
            pass


def _avg_wohnflaeche_pro_we(datensatz: GeneralisierterDatensatz) -> Optional[float]:
    """Durchschnittliche Wohnflaeche **pro WE** — fuer €/m²-Berechnung.

    Portal-Adapter (CHECK24/Homeday/Interhyp) bewerten EINE
    repraesentative Wohneinheit. Der Marktwert ist daher pro WE,
    nicht fuer das gesamte MFH. Beispiel: Interhyp 130k bei 73qm
    AVG-Wohnflaeche = 1781 €/m² (plausibel) — bei 292qm
    Gesamtwohnflaeche waere 445 €/m² (unplausibel).
    """
    # Direkt als Attribut
    avg = getattr(datensatz, "avg_wohnflaeche_qm", None)
    if avg:
        return float(avg)
    # Aus we_liste (Objekt-Variante)
    if hasattr(datensatz, "we_liste") and datensatz.we_liste:
        try:
            arr = [we.wohnflaeche_qm for we in datensatz.we_liste]
            return float(sum(arr)) / len(arr)
        except Exception:
            pass
    # Aus wohnflaechen_qm-Liste
    wf = getattr(datensatz, "wohnflaechen_qm", None)
    if wf:
        try:
            return float(sum(wf)) / len(wf)
        except Exception:
            pass
    # Fallback: gesamtwohnflaeche / anzahl_we
    gesamt = getattr(datensatz, "gesamtwohnflaeche_qm", None)
    n = getattr(datensatz, "anzahl_we", None)
    if gesamt and n:
        try:
            return float(gesamt) / int(n)
        except Exception:
            pass
    return None


def _gesamtwohnflaeche(datensatz: GeneralisierterDatensatz) -> Optional[float]:
    """Summe der WE-Wohnflaechen — fuer absolute Marktwert-Vergleiche."""
    qm = getattr(datensatz, "gesamtwohnflaeche_qm", None)
    if qm:
        return float(qm)
    if hasattr(datensatz, "we_liste") and datensatz.we_liste:
        try:
            return float(sum(we.wohnflaeche_qm for we in datensatz.we_liste))
        except Exception:
            pass
    wf = getattr(datensatz, "wohnflaechen_qm", None)
    if wf:
        try:
            return float(sum(wf))
        except Exception:
            pass
    avg = getattr(datensatz, "avg_wohnflaeche_qm", None)
    n = getattr(datensatz, "anzahl_we", None)
    if avg and n:
        try:
            return float(avg) * int(n)
        except Exception:
            pass
    return None


def _compute_eur_per_qm(portal_out: dict, wohnflaeche_qm: Optional[float]) -> Optional[float]:
    """Leitet €/m² aus Portal-Output ab.

    Pfad 1: `extra.eur_per_qm` (Homeday — natives €/m²-Feld).
    Pfad 2: `marktwert_eur_mittel / wohnflaeche` (CHECK24, Interhyp).
    """
    if not isinstance(portal_out, dict):
        return None
    if portal_out.get("status") not in ("ok", "partial"):
        return None
    # Pfad 1: natives €/m²-Feld im extra-Slot (Homeday)
    extra = portal_out.get("extra") or {}
    direct = extra.get("eur_per_qm")
    if direct:
        try:
            return float(direct)
        except Exception:
            pass
    # Pfad 2: aus absolutem Marktwert pro WE
    mw = portal_out.get("marktwert_eur_mittel")
    if mw and wohnflaeche_qm:
        return round(float(mw) / float(wohnflaeche_qm), 2)
    return None


def _extract_immometrica_eur_per_qm(immo_out: dict) -> Optional[float]:
    """Holt PLZ-ETW €/m² aus dem Immometrica-extra-Slot.

    Immometrica liefert mehrere Configs (PLZ + Stadt × ETW/Mietwohnung/MFH).
    Fuer Modul-0-Excel-Befuellung nutzen wir PRIMAER PLZ-ETW (lokal, ETW).
    Stadt-ETW wird im JSON-Output behalten, aber nicht in Excel I14
    geschrieben — KALKU!I17 ist der Grundstuecksmarktbericht (Notion-DB).
    """
    if not isinstance(immo_out, dict):
        return None
    extra = immo_out.get("extra") or {}
    slot = extra.get("plz_etw")
    if isinstance(slot, dict):
        uebersicht = slot.get("uebersicht") or {}
        val = uebersicht.get("median_preis_eur_per_qm")
        if val is not None:
            try:
                return float(val)
            except Exception:
                pass
    return None


def _compute_konsens(values: list[float]) -> dict:
    """Konsens-Median + Spread (Max-Min) + Prozent."""
    out = {
        "konsens_median_eur": None,
        "konsens_spread_eur": None,
        "konsens_spread_prozent": None,
        "anzahl_quellen": 0,
        "label": "keine Quellen verfuegbar",
    }
    clean = [v for v in values if v is not None and v > 0]
    if not clean:
        return out
    median_v = statistics.median(clean)
    spread = max(clean) - min(clean)
    spread_pct = (spread / median_v) * 100 if median_v else 0
    out.update({
        "konsens_median_eur": int(round(median_v)),
        "konsens_spread_eur": int(round(spread)),
        "konsens_spread_prozent": round(spread_pct, 1),
        "anzahl_quellen": len(clean),
        "label": (f"{len(clean)} Quellen, Median {int(round(median_v)):,} €, "
                  f"Spread {round(spread_pct, 1)}%").replace(",", "."),
    })
    return out


def run_all_portals(
    datensatz: GeneralisierterDatensatz,
    *,
    headless: bool = True,
    kaufabsicht: str = "kauf",
    verbose: bool = False,
) -> dict:
    """Ruft alle 4 Portale parallel auf + aggregiert zu Konsens.

    Returns: dict mit 'portale', 'marktwert', 'eur_per_qm', 'errors'.
    """
    wohnflaeche_gesamt = _gesamtwohnflaeche(datensatz)
    wohnflaeche_avg_we = _avg_wohnflaeche_pro_we(datensatz)

    # 4 parallele Calls
    portale: dict[str, dict] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(_run_portalbase, "check24", datensatz, headless, kaufabsicht, verbose): "check24",
            ex.submit(_run_portalbase, "homeday", datensatz, headless, kaufabsicht, verbose): "homeday",
            ex.submit(_run_portalbase, "interhyp", datensatz, headless, kaufabsicht, verbose): "interhyp",
            ex.submit(_run_immometrica_wrap, datensatz, headless): "immometrica",
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                portale[name] = fut.result()
            except Exception as e:
                portale[name] = {
                    "status": "error",
                    "portal": name,
                    "error_message": f"{type(e).__name__}: {e}",
                }
            if portale[name].get("status") not in ("ok", "partial"):
                errors.append(f"{name}: {portale[name].get('error_message') or portale[name].get('status')}")

    # €/m² pro Quelle ableiten — durch avg_wohnflaeche PRO WE, nicht Gesamt!
    # PortalBase-Adapter (Homeday/CHECK24/Interhyp) bewerten 1 repraesentative WE.
    eur_per_qm_homeday = _compute_eur_per_qm(portale.get("homeday", {}), wohnflaeche_avg_we)
    eur_per_qm_check24 = _compute_eur_per_qm(portale.get("check24", {}), wohnflaeche_avg_we)
    eur_per_qm_interhyp = _compute_eur_per_qm(portale.get("interhyp", {}), wohnflaeche_avg_we)
    eur_per_qm_immo = _extract_immometrica_eur_per_qm(portale.get("immometrica", {}))

    # 5 Excel-Slots in Sheet-Reihenfolge (KALKU!I13–I17):
    # I13 Homeday | I14 Immometrica | I15 CHECK24 | I16 Interhyp | I17 GMB.
    # GMB (Grundstuecksmarktbericht) wird vom Orchestrator NICHT geliefert —
    # Modul 0 macht den Notion-DB-Lookup und fuellt nach (Key bleibt hier
    # null, Median ueber die 4 nicht-null Portal-Werte).
    eur_per_qm = {
        "homeday":                 eur_per_qm_homeday,
        "immometrica":             eur_per_qm_immo,
        "check24":                 eur_per_qm_check24,
        "interhyp":                eur_per_qm_interhyp,
        "grundstuecksmarktbericht": None,
    }
    qm_values = [v for v in eur_per_qm.values() if v is not None]
    eur_per_qm["median"] = round(statistics.median(qm_values), 2) if qm_values else None

    # Marktwert-Konsens — alle pro WE (Adapter-Werte sind pro repraesentative WE).
    # Immometrica wird auf pro-WE umgerechnet: €/m² × avg_wohnflaeche.
    marktwert_values = [
        portale.get("check24", {}).get("marktwert_eur_mittel"),
        portale.get("homeday", {}).get("marktwert_eur_mittel"),
        portale.get("interhyp", {}).get("marktwert_eur_mittel"),
    ]
    if eur_per_qm_immo and wohnflaeche_avg_we:
        marktwert_values.append(eur_per_qm_immo * wohnflaeche_avg_we)
    marktwert_konsens = _compute_konsens([v for v in marktwert_values if v])

    # Status final
    ok_count = sum(1 for p in portale.values() if p.get("status") in ("ok", "partial"))
    if ok_count == 4:
        status = "ok"
    elif ok_count > 0:
        status = "partial"
    else:
        status = "error"

    result = {
        "status": status,
        "generalisierter_datensatz": asdict(datensatz),
        "wohnflaeche_qm_gesamt": wohnflaeche_gesamt,
        "wohnflaeche_qm_avg_we": wohnflaeche_avg_we,
        "marktwert_referenz": "pro repraesentative WE",
        "portale": portale,
        "marktwert": marktwert_konsens,
        "eur_per_qm": eur_per_qm,
        "errors": errors,
    }

    # Health-Check inline schreiben — sichtbar fuer parallele Debug-Session.
    # Beschaedigt die Analyse NICHT (Werte bleiben im Result-Dict, fehlende
    # Werte sind null + 'manuell eingeben'-Hinweis).
    try:
        _write_health_check_report(datensatz, result)
    except Exception as e:
        print(f"WARN: health-check report fehlgeschlagen: {e}",
              file=sys.stderr, flush=True)

    return result


def _write_health_check_report(datensatz: GeneralisierterDatensatz, result: dict) -> None:
    """Schreibt einen Markdown-Health-Report nach jedem --alle-Lauf.

    Output-Pfad: tools/portal-bewertung/runs/health-check_<ts>.md
    Bei Fehlern zusaetzlich: runs/health-check_<ts>_FAIL.md mit Debug-Prompt
    fuer parallele Debug-Session (User-Workflow: Fenster nebenan, Analyse
    laeuft weiter).
    """
    from datetime import datetime, timedelta, timezone
    runs_dir = Path(__file__).resolve().parent / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%dT%H%M%S")
    addr = f"{datensatz.strasse} {datensatz.hausnr}, {datensatz.plz} {datensatz.ort}"

    portale = result.get("portale", {})
    eur_per_qm = result.get("eur_per_qm", {})
    errors = result.get("errors", []) or []
    has_failures = bool(errors) or result.get("status") in ("partial", "error")

    lines = [
        f"# Health-Check Portal-Orchestrator — {ts}",
        "",
        f"**Adresse:** {addr}",
        f"**Baujahr:** {datensatz.baujahr}",
        f"**Status final:** `{result.get('status')}`",
        "",
        "## Modul-Status",
        "",
        "| Portal | Status | €/m² | Fehler |",
        "|---|---|---|---|",
    ]
    portal_to_qm_key = {
        "homeday": "homeday",
        "immometrica": "immometrica",
        "check24": "check24",
        "interhyp": "interhyp",
    }
    for name in ("homeday", "immometrica", "check24", "interhyp"):
        p = portale.get(name) or {}
        st = p.get("status") or "missing"
        qm_key = portal_to_qm_key.get(name)
        qm_val = eur_per_qm.get(qm_key) if qm_key else None
        qm_str = f"{qm_val:.2f}" if qm_val is not None else "—"
        err = p.get("error_message") or p.get("error_code") or ""
        err_short = (err[:120] + "…") if len(err) > 120 else err
        lines.append(f"| {name} | {st} | {qm_str} | {err_short} |")

    # GMB ist Notion-Lookup — wird hier nicht vom Orchestrator gefuellt
    gmb_val = eur_per_qm.get("grundstuecksmarktbericht")
    gmb_str = f"{gmb_val:.2f}" if gmb_val is not None else "(Modul 0 fuellt aus Notion)"
    lines.append(f"| grundstuecksmarktbericht | n/a | {gmb_str} | — |")

    lines += [
        "",
        f"**Konsens-Median €/m²:** {eur_per_qm.get('median')}",
        f"**Marktwert-Konsens €:** {(result.get('marktwert') or {}).get('konsens_median_eur')}",
        "",
    ]

    if has_failures:
        lines += [
            "## ⚠️ Fehlerhafte Modules",
            "",
            "Werte sind im Output-JSON als `null` markiert — Analyse NICHT",
            "beschädigt. Fehlende Werte bitte **manuell eintragen** oder",
            "im parallelen Debug-Fenster fixen.",
            "",
        ]
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    txt = "\n".join(lines)
    out_path = runs_dir / f"health-check_{ts}.md"
    out_path.write_text(txt, encoding="utf-8")

    if has_failures:
        fail_path = runs_dir / f"health-check_{ts}_FAIL.md"
        fail_lines = [
            f"# ⚠️ Portal-Orchestrator FAIL — {ts}",
            "",
            f"**Adresse:** {addr}",
            "",
            "## Fehlende/fehlerhafte Module",
            "",
        ]
        for e in errors:
            fail_lines.append(f"- {e}")
        fail_lines += [
            "",
            "## Debug-Prompt für neue Session (parallel zur laufenden Analyse)",
            "",
            "Öffne ein NEUES Chat-Fenster mit Claude Code in",
            "`c:\\meine-projekte\\Immobilien\\Aufteiler\\tools\\portal-bewertung\\`",
            "und sende folgenden Prompt:",
            "",
            "```",
            f"Health-Check vom {ts} hat fehlerhafte Portale gemeldet:",
            "",
        ]
        for e in errors:
            fail_lines.append(e)
        fail_lines += [
            "",
            f"Datei: runs/health-check_{ts}_FAIL.md",
            f"Adresse: {addr}, Baujahr {datensatz.baujahr}",
            "",
            "Bitte den/die fehlerhaften Adapter im Solo-Test fixen",
            "(`python m00_portal_pricer.py --portal <name> ...`), commit + push.",
            "Die Haupt-Analyse läuft parallel im anderen Fenster weiter,",
            "Werte werden manuell nachgetragen.",
            "```",
            "",
        ]
        fail_path.write_text("\n".join(fail_lines), encoding="utf-8")
        print(f"WARN: Health-Check FAIL geschrieben: {fail_path.name}",
              file=sys.stderr, flush=True)
