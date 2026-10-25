"""Notion-Upload: Sub-Page-Body (GMB) und DB-Zeilen-Payload (Mietspiegel) bauen.

Echte Notion-Schreiben passieren über MCP-Tools im orchestrator.py.
Dieses Modul baut nur die Payloads.
"""

from datetime import datetime
from typing import Optional, Dict, Any


PREISDATENBANK_PARENT_ID = "3310ae59-38e4-81f1-ad36-e8bd809d437a"
MIETSPIEGEL_DB_ID = "8b000923-d5ee-45a4-8f6a-e7f3bf81f20e"


def build_gmb_page_title(stadt: str, jahr: int) -> str:
    return f"📍 {stadt} Marktdaten (GMB {jahr})"


def build_gmb_page_body(
    raw: Dict[str, Any],
    stadt: str,
    stadtteil: Optional[str],
    baujahr: Optional[int],
    konfidenz_score: int,
    pdf_url: str,
    anfrage_adresse: str,
    gelieferter_wert: Optional[float],
) -> str:
    """Markdown-Body im Bochum-Stil."""
    q = raw.get("quelldokument", {})
    parts = [
        f"**Stand: {_today()} (Auto-Fallback)**",
        "",
        "# Quelldokument",
        f"- Titel: {q.get('titel', '–')}",
        f"- Autor: {q.get('autor', '–')}",
        f"- Erschienen: {q.get('erschienen', '–')}",
        f"- Quelle-URL: {pdf_url}",
        f"- Datenbasis: {q.get('datenbasis', '–')}",
        "",
    ]

    if raw.get("mfh_einkauf_baujahr"):
        parts += ["# MFH-Einkaufspreise (Transaktionspreise)", "## MFH nach Baujahr", _build_table(
            raw["mfh_einkauf_baujahr"],
            headers=["baujahr", "n_2024", "qm_wfl_avg", "eur_qm_avg", "eur_qm_min", "eur_qm_max", "s"],
            labels=["Baujahr", "n", "Ø m² Wfl.", "Ø EUR/m²", "Min", "Max", "s"]
        ), ""]

    if raw.get("etw_exit_baujahr"):
        parts += ["# ETW-Verkaufspreise", _build_table(
            raw["etw_exit_baujahr"],
            headers=["baujahr", "n_2024", "qm_wfl_avg", "eur_qm_avg", "eur_qm_min", "eur_qm_max"],
            labels=["Baujahr", "n", "Ø m² Wfl.", "Ø EUR/m²", "Min", "Max"]
        ), ""]

    if raw.get("bodenrichtwerte"):
        parts += ["# Bodenrichtwerte", _build_table(
            raw["bodenrichtwerte"],
            headers=["lage", "eur_qm", "hinweis"],
            labels=["Lage", "EUR/m²", "Hinweis"]
        ), ""]

    if raw.get("lage_eur_qm_stadtteil"):
        parts += ["# Lage-Differenzierung", _build_table(
            raw["lage_eur_qm_stadtteil"],
            headers=["stadtteil", "eur_qm_avg", "wohnlage_klasse"],
            labels=["Stadtteil", "ETW-Mittel EUR/m²", "Wohnlage-Klasse"]
        ), ""]

    parts += [
        "# Auto-Fallback-Metadaten",
        f"- Trigger: Modul-0 Schritt C.1, Lookup für {stadt} {stadtteil or '(ohne Stadtteil)'}",
        f"- Konfidenz: {konfidenz_score} %",
        f"- Extrahiert: {_now()}",
        f"- Anfrage-Adresse: {anfrage_adresse}",
        f"- Gelieferter Wert: {gelieferter_wert if gelieferter_wert is not None else 'null'} EUR/m² (Baujahres-Klasse {baujahr or '?'}, Stadtteil {stadtteil or '?'})",
    ]
    return "\n".join(parts)


def build_mietspiegel_row_payload(
    raw: Dict[str, Any],
    stadt: str,
    pdf_url: str,
    vollstaendigkeit: str,
) -> Dict[str, Any]:
    """Payload für MCP-Notion `create_pages` mit Data-Source `MIETSPIEGEL_DB_ID`.

    Felder mappen auf DB-Spalten in der Mietspiegel-NRW-DB.
    """
    q = raw.get("quelldokument", {})
    kappung = raw.get("kappungsgrenze_prozent")
    kappung_str = f"{kappung}%" if kappung in (15, 20) else None

    payload = {
        "Stadt": stadt,
        "Quelle PDF": pdf_url,
        "Vollstaendigkeit": vollstaendigkeit,
    }
    if kappung_str:
        payload["Kappungsgrenze"] = kappung_str
    if "mietpreisbremse" in raw and raw["mietpreisbremse"] is not None:
        payload["Mietpreisbremse"] = bool(raw["mietpreisbremse"])
    if raw.get("mietspiegel_typ"):
        payload["Mietspiegel-Typ"] = raw["mietspiegel_typ"]
    if q.get("stand"):
        payload["Stand"] = q["stand"]
    return payload


def build_mietspiegel_page_body(
    raw: Dict[str, Any],
    stadt: str,
    baujahr: Optional[int],
    konfidenz_score: int,
    pdf_url: str,
    gelieferter_wert: Optional[float],
) -> str:
    """Markdown-Body, der innerhalb der DB-Zeilen-Page geschrieben wird."""
    q = raw.get("quelldokument", {})
    parts = [
        f"**Stand: {_today()} (Auto-Fallback)**",
        "",
        "# Quelldokument",
        f"- Titel: {q.get('titel', '–')}",
        f"- Stand: {q.get('stand', '–')}",
        f"- Quelle-URL: {pdf_url}",
        "",
    ]
    if raw.get("basis_eur_qm_baujahr"):
        parts += ["# Basis-€/m² nach Baujahres-Klasse", _build_table(
            raw["basis_eur_qm_baujahr"],
            headers=["baujahr", "eur_qm", "spanne_min", "spanne_max"],
            labels=["Baujahres-Klasse", "Basis-€/m²", "Spanne Min", "Spanne Max"]
        ), ""]
    if raw.get("lage_korrekturen"):
        parts += ["# Lage-Korrekturen", _build_table(
            raw["lage_korrekturen"],
            headers=["klasse", "korrektur_prozent", "beispielstrassen"],
            labels=["Klasse", "Korrektur %", "Beispiel-Straßen"]
        ), ""]
    if raw.get("ausstattungs_zuschlaege"):
        parts += ["# Ausstattungs-Zuschläge (4.3-4.9)", _build_table(
            raw["ausstattungs_zuschlaege"],
            headers=["ausstattung", "zuschlag_eur_qm"],
            labels=["Ausstattung", "Zuschlag €/m²"]
        ), ""]
    parts += [
        "# Auto-Fallback-Metadaten",
        f"- Trigger: Modul-4 Abschnitt 2, Lookup für {stadt}",
        f"- Konfidenz: {konfidenz_score} %",
        f"- Extrahiert: {_now()}",
        f"- Anfrage-Stadt: {stadt}, Baujahr: {baujahr}",
        f"- Gelieferter Wert: Basis-€/m² {gelieferter_wert if gelieferter_wert is not None else 'null'}",
    ]
    return "\n".join(parts)


def _build_table(rows, headers, labels):
    head = "| " + " | ".join(labels) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body_lines = []
    for r in rows:
        vals = []
        for h in headers:
            v = r.get(h, "–")
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            vals.append(str(v))
        body_lines.append("| " + " | ".join(vals) + " |")
    return "\n".join([head, sep] + body_lines)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
