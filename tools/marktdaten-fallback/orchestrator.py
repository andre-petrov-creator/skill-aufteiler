"""Top-Level Orchestrator: Find -> Download -> Extract -> Upload -> Return.

Wird vom Sub-Skill aufgerufen -- entweder direkt aus Python heraus oder via CLI.

CLI:
  python orchestrator.py --mode gmb --stadt Bochum --stadtteil Eppendorf \
                         --baujahr 1965 --interaktiv 0 --slug welperstr-39-hattingen
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import find
import download
import extract
import notion_upload
from konfidenz import aggregate_konfidenz, gate_passed


def run_fallback(
    mode: str,
    stadt: str,
    stadtteil: Optional[str],
    baujahr: Optional[int],
    interaktiv: bool,
    slug: str,
) -> Dict[str, Any]:
    """Top-Level Pipeline. Returnt Schema gemaess Spec Section 2."""
    assert mode in ("gmb", "mietspiegel"), f"unknown mode: {mode}"

    # 1. FIND
    if mode == "gmb":
        find_result = find.find_gmb_source(stadt=stadt, stadtteil=stadtteil, baujahr=baujahr)
    else:
        find_result = find.find_mietspiegel_source(stadt=stadt)

    trail = find_result["quellen_trail"]

    # Notion-Treffer-Short-Circuit (GMB): Werte direkt aus Notion holen, kein Download
    if mode == "gmb" and find_result.get("notion_page_id") and find_result.get("pdf_url") is None:
        # Notion-Page existiert -- die Werte sind dort. Modul-0 muss die Page noch
        # selbst lesen (das passt zum heutigen Modul-0-C.1-Flow); wir liefern nur
        # die Page-ID + Konfidenz zurueck und ueberlassen es dem Modul, den EUR/m2 aus
        # der Page zu extrahieren. Konfidenz 60 reicht fuer >=70 nicht -- Modul muss
        # ggf. mit Werten weitermachen, die es selbst extrahiert.
        konfidenz = aggregate_konfidenz(trail)
        return _build_result(
            eur_per_qm=None, zusatzfelder={}, konfidenz=konfidenz, trail=trail,
            notion_target_id=find_result["notion_page_id"],
            begruendung=f"Notion-Page fuer {stadt} GMB existiert: {find_result['notion_page_id']}. Modul liest EUR/m2 direkt aus Page.",
            fail_reason=None
        )

    if find_result.get("pdf_url") is None:
        konfidenz = aggregate_konfidenz(trail)
        return _build_result(
            eur_per_qm=None, zusatzfelder={}, konfidenz=konfidenz, trail=trail,
            notion_target_id=None,
            begruendung=f"Keine offizielle PDF-Quelle fuer {mode}/{stadt} gefunden. Quellen-Trail-Laenge: {len(trail)}.",
            fail_reason="Alle Quellen erschoepft, keine offizielle PDF-URL gefunden."
        )

    # 2. DOWNLOAD (mit Cache)
    pdf_url = find_result["pdf_url"]
    jahr = _detect_year_from_url(pdf_url) or datetime.now().year
    cache_file = download.cache_path_for(stadt=stadt, typ=mode, jahr=jahr)
    if not download.cache_hit(cache_file, notion_stand_iso=None):
        try:
            download.download_pdf(pdf_url, cache_file)
        except Exception as e:
            trail.append({"typ": "fail", "quelle": pdf_url, "ergebnis": f"Download-Fehler: {e}", "bonus": 0})
            return _build_result(
                eur_per_qm=None, zusatzfelder={}, konfidenz=aggregate_konfidenz(trail), trail=trail,
                notion_target_id=None,
                begruendung=f"Download fehlgeschlagen fuer {pdf_url}: {e}",
                fail_reason=f"download_failed: {e}"
            )

    # 3. EXTRACT
    try:
        if mode == "gmb":
            ext = extract.extract_gmb(pdf_path=cache_file, stadt=stadt, stadtteil=stadtteil, baujahr=baujahr)
        else:
            ext = extract.extract_mietspiegel(pdf_path=cache_file, stadt=stadt, baujahr=baujahr)
    except Exception as e:
        trail.append({"typ": "fail", "quelle": str(cache_file), "ergebnis": f"Extract-Fehler: {e}", "bonus": 0})
        return _build_result(
            eur_per_qm=None, zusatzfelder={}, konfidenz=aggregate_konfidenz(trail), trail=trail,
            notion_target_id=None,
            begruendung=f"Extract fehlgeschlagen: {e}",
            fail_reason=f"extract_failed: {e}"
        )

    konfidenz = aggregate_konfidenz(trail)

    # Konfidenz-Gate: <70 -> null + fail_reason (kein Notion-Upload)
    if not gate_passed(konfidenz):
        return _build_result(
            eur_per_qm=None if not ext.get("eur_per_qm") else ext["eur_per_qm"],
            zusatzfelder=ext.get("zusatzfelder", {}),
            konfidenz=konfidenz, trail=trail,
            notion_target_id=None,
            begruendung=f"Konfidenz {konfidenz} < 70 -- kein Notion-Upload, Wert wird nicht autonom gesetzt.",
            fail_reason=f"konfidenz_below_gate: score={konfidenz}"
        )

    # 4. UPLOAD
    if mode == "gmb":
        target_id = _notion_upload_gmb_page(
            raw=ext["raw"], stadt=stadt, stadtteil=stadtteil, baujahr=baujahr,
            konfidenz_score=konfidenz, pdf_url=pdf_url,
            anfrage_adresse=f"{slug}", gelieferter_wert=ext.get("eur_per_qm"), jahr=jahr,
        )
    else:
        target_id = _notion_upsert_mietspiegel_row(
            raw=ext["raw"], stadt=stadt, pdf_url=pdf_url, konfidenz_score=konfidenz,
            baujahr=baujahr, gelieferter_wert=ext.get("eur_per_qm"),
        )

    # 5. RETURN
    return _build_result(
        eur_per_qm=ext.get("eur_per_qm"),
        zusatzfelder=ext.get("zusatzfelder", {}),
        konfidenz=konfidenz,
        trail=trail,
        notion_target_id=target_id,
        begruendung=_build_begruendung(mode, stadt, stadtteil, ext, konfidenz, pdf_url),
        fail_reason=None
    )


def _build_result(eur_per_qm, zusatzfelder, konfidenz, trail, notion_target_id, begruendung, fail_reason):
    return {
        "ergebnis": {"eur_per_qm": eur_per_qm, "zusatzfelder": zusatzfelder},
        "konfidenz_score": konfidenz,
        "quellen_trail": [{"typ": t["typ"], "quelle": t["quelle"], "ergebnis": t["ergebnis"]} for t in trail],
        "notion_target_id": notion_target_id,
        "begruendung": begruendung,
        "fail_reason": fail_reason,
    }


def _build_begruendung(mode, stadt, stadtteil, ext, konfidenz, pdf_url) -> str:
    if mode == "gmb":
        return (
            f"GMB-Werte fuer {stadt} {stadtteil or '(Stadt-Ebene)'} aus offizieller Quelle "
            f"{pdf_url} extrahiert. Gelieferter ETW-EUR/m2: {ext.get('eur_per_qm')}. "
            f"Konfidenz {konfidenz} %."
        )
    return (
        f"Mietspiegel-Werte fuer {stadt} aus {pdf_url} extrahiert. "
        f"Basis-EUR/m2: {ext.get('eur_per_qm')}. Kappung "
        f"{ext.get('zusatzfelder', {}).get('kappungsgrenze_prozent')}%. "
        f"Konfidenz {konfidenz} %."
    )


def _detect_year_from_url(url: str) -> Optional[int]:
    import re
    m = re.search(r"(20\d{2})", url)
    return int(m.group(1)) if m else None


def _notion_upload_gmb_page(raw, stadt, stadtteil, baujahr, konfidenz_score, pdf_url,
                            anfrage_adresse, gelieferter_wert, jahr) -> Optional[str]:
    """Upload via MCP-Notion-Tools. In Tests gemockt."""
    title = notion_upload.build_gmb_page_title(stadt=stadt, jahr=jahr)
    body = notion_upload.build_gmb_page_body(
        raw=raw, stadt=stadt, stadtteil=stadtteil, baujahr=baujahr,
        konfidenz_score=konfidenz_score, pdf_url=pdf_url,
        anfrage_adresse=anfrage_adresse, gelieferter_wert=gelieferter_wert,
    )
    # Echter MCP-Call: passiert im Sub-Skill SKILL.md (claude --print), nicht hier.
    # Hier nur Payload-Vorbereitung -- Skill nimmt das JSON, ruft MCP-Tool auf.
    print(json.dumps({
        "action": "notion_create_page",
        "parent_page_id": notion_upload.PREISDATENBANK_PARENT_ID,
        "title": title,
        "body_markdown": body,
    }, ensure_ascii=False))
    return None  # echte Page-ID kommt vom Skill via MCP-Aufruf zurueck


def _notion_upsert_mietspiegel_row(raw, stadt, pdf_url, konfidenz_score, baujahr, gelieferter_wert) -> Optional[str]:
    """Upsert DB-Zeile. In Tests gemockt."""
    payload = notion_upload.build_mietspiegel_row_payload(
        raw=raw, stadt=stadt, pdf_url=pdf_url, vollstaendigkeit="komplett",
    )
    body = notion_upload.build_mietspiegel_page_body(
        raw=raw, stadt=stadt, baujahr=baujahr, konfidenz_score=konfidenz_score,
        pdf_url=pdf_url, gelieferter_wert=gelieferter_wert,
    )
    print(json.dumps({
        "action": "notion_upsert_db_row",
        "data_source_url": f"collection://{notion_upload.MIETSPIEGEL_DB_ID}",
        "row_payload": payload,
        "body_markdown": body,
    }, ensure_ascii=False))
    return None


def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["gmb", "mietspiegel"], required=True)
    p.add_argument("--stadt", required=True)
    p.add_argument("--stadtteil", default=None)
    p.add_argument("--baujahr", type=int, default=None)
    p.add_argument("--interaktiv", type=int, default=0)
    p.add_argument("--slug", required=True)
    args = p.parse_args()
    result = run_fallback(
        mode=args.mode, stadt=args.stadt, stadtteil=args.stadtteil,
        baujahr=args.baujahr, interaktiv=bool(args.interaktiv), slug=args.slug,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ergebnis", {}).get("eur_per_qm") is not None else 1


if __name__ == "__main__":
    sys.exit(_cli())
