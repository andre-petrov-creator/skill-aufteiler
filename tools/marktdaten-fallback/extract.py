"""EXTRACT-Phase: Opus 4.7 liest PDF, returnt Schema-konformes JSON."""

import base64
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List


KONFIDENZ_PRO_FELD_MIN = 0.6
OPUS_MODEL = "claude-opus-4-7"


def extract_gmb(pdf_path: Path, stadt: str, stadtteil: Optional[str], baujahr: Optional[int]) -> Dict[str, Any]:
    """Extrahiere GMB-Werte aus PDF. Liefert €/m² für die gefragte Stadt-/Stadtteil-/Baujahr-Kombi."""
    raw = _call_opus_extract(pdf_path, mode="gmb", stadt=stadt, stadtteil=stadtteil, baujahr=baujahr)

    eur_per_qm = _pick_etw_eur_per_qm(raw, baujahr=baujahr, stadtteil=stadtteil)
    konfidenz = _aggregate_table_konfidenz(raw, table_keys=["etw_exit_baujahr"])

    # Konfidenz pro Feld < 0.6 → Wert auf null
    if konfidenz < KONFIDENZ_PRO_FELD_MIN:
        eur_per_qm = None

    # Stadtteil-Match: wenn lage-tabelle existiert und Stadtteil nicht matcht, Konfidenz reduzieren
    lage_table = raw.get("lage_eur_qm_stadtteil") or []
    if stadtteil and lage_table:
        match = next((e for e in lage_table if _norm(e.get("stadtteil", "")) == _norm(stadtteil)), None)
        if not match:
            # User-Regel: kein Stadt-Mittelwert als Fallback → null
            eur_per_qm = None
            konfidenz = min(konfidenz, 0.5)

    return {
        "eur_per_qm": eur_per_qm,
        "zusatzfelder": {},
        "konfidenz_score": int(round(konfidenz * 100)),
        "raw": raw,
    }


def extract_mietspiegel(pdf_path: Path, stadt: str, baujahr: Optional[int]) -> Dict[str, Any]:
    """Extrahiere Mietspiegel-Werte. Liefert Basis-€/m² + Kappung + Mietpreisbremse + Typ."""
    raw = _call_opus_extract(pdf_path, mode="mietspiegel", stadt=stadt, baujahr=baujahr)

    eur_per_qm = _pick_mietspiegel_basis(raw, baujahr=baujahr)
    konfidenz = _aggregate_table_konfidenz(raw, table_keys=["basis_eur_qm_baujahr"])

    if konfidenz < KONFIDENZ_PRO_FELD_MIN:
        eur_per_qm = None

    return {
        "eur_per_qm": eur_per_qm,
        "zusatzfelder": {
            "kappungsgrenze_prozent": raw.get("kappungsgrenze_prozent"),
            "mietpreisbremse": raw.get("mietpreisbremse"),
            "mietspiegel_typ": raw.get("mietspiegel_typ"),
        },
        "konfidenz_score": int(round(konfidenz * 100)),
        "raw": raw,
    }


def _pick_etw_eur_per_qm(raw: Dict[str, Any], baujahr: Optional[int], stadtteil: Optional[str]) -> Optional[float]:
    """ETW-Exit-Wert für Baujahres-Klasse. Wenn Lage-Tabelle vorhanden und Stadtteil-Match: dieser Wert."""
    if stadtteil and raw.get("lage_eur_qm_stadtteil"):
        m = next((e for e in raw["lage_eur_qm_stadtteil"] if _norm(e.get("stadtteil", "")) == _norm(stadtteil)), None)
        if m and m.get("eur_qm_avg"):
            return float(m["eur_qm_avg"])
    table = raw.get("etw_exit_baujahr") or []
    if baujahr is None:
        return None
    for entry in table:
        if _baujahr_in_range(baujahr, entry.get("baujahr", "")):
            return float(entry.get("eur_qm_avg") or 0) or None
    return None


def _pick_mietspiegel_basis(raw: Dict[str, Any], baujahr: Optional[int]) -> Optional[float]:
    table = raw.get("basis_eur_qm_baujahr") or []
    if baujahr is None:
        return None
    for entry in table:
        if _baujahr_in_range(baujahr, entry.get("baujahr", "")):
            return float(entry.get("eur_qm") or 0) or None
    return None


def _baujahr_in_range(year: int, range_str: str) -> bool:
    """Parse 'vor 1949', '1949-1977', '1990-1999', etc."""
    s = range_str.strip().lower()
    m_vor = re.match(r"^vor\s+(\d{4})$", s)
    if m_vor:
        return year < int(m_vor.group(1))
    m_range = re.match(r"^(\d{4})\s*[-–]\s*(\d{4})$", s)
    if m_range:
        return int(m_range.group(1)) <= year <= int(m_range.group(2))
    m_single = re.match(r"^(\d{4})$", s)
    if m_single:
        return year == int(m_single.group(1))
    return False


def _aggregate_table_konfidenz(raw: Dict[str, Any], table_keys: List[str]) -> float:
    """Mittlere Konfidenz der relevanten Tabellen."""
    konf_map = raw.get("konfidenz_pro_tabelle") or {}
    vals = [float(konf_map.get(k, 0)) for k in table_keys]
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.lower())


def _call_opus_extract(pdf_path: Path, mode: str, **kwargs) -> Dict[str, Any]:
    """Echter Opus-4.7-Call via `claude --print --model claude-opus-4-7` mit PDF als Vision-Input.

    Prompt-Skelett siehe Doc marktdaten-fallback.md. Wird in Tests gemockt.
    """
    schema_hint = _schema_hint_for_mode(mode)
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")

    prompt = f"""Du bekommst eine {('GMB' if mode == 'gmb' else 'Mietspiegel')}-PDF.
Stadt: {kwargs.get('stadt')}
Stadtteil: {kwargs.get('stadtteil', 'n/a')}
Baujahr: {kwargs.get('baujahr', 'n/a')}

Extrahiere die unten genannten Tabellen 1:1 als JSON.

Output-Schema:
{schema_hint}

WICHTIG: konfidenz_pro_tabelle pro Tabelle 0.0–1.0. Tabellen, die du nicht zuverlässig
extrahieren konntest, lass weg (nicht raten). Wenn die Stadt/Stadtteil/Baujahr-Kombi
keinen klaren Wert hergibt: leeres Array für die Tabelle, Konfidenz 0.

Antworte NUR mit dem JSON, kein Markdown-Wrapper, kein Kommentar.
"""

    # Echter Aufruf: claude CLI mit File-Attachment-Mechanik. Hier vereinfacht
    # gezeigt — die orchestrator.py-Task verdrahtet das mit `claude --print` und
    # passenden Argumenten für PDF-Bytes-Übergabe.
    cmd = ["claude", "--print", "--model", OPUS_MODEL, "--input-format", "json"]
    payload = json.dumps({
        "messages": [{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    })
    result = subprocess.run(cmd, input=payload, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"opus call failed: {result.stderr}")
    return json.loads(result.stdout)


def _schema_hint_for_mode(mode: str) -> str:
    if mode == "gmb":
        return """{
  "quelldokument": {"titel": "...", "autor": "...", "erschienen": "Monat YYYY", "datenbasis": "..."},
  "mfh_einkauf_baujahr": [{"baujahr": "vor 1950|1950-1974|...", "n_2024": int, "qm_wfl_avg": int, "eur_qm_avg": int, "eur_qm_min": int, "eur_qm_max": int, "s": int}],
  "etw_exit_baujahr": [{"baujahr": "vor 1950|1950-1959|...", "n_2024": int, "qm_wfl_avg": int, "eur_qm_avg": int, "eur_qm_min": int, "eur_qm_max": int}],
  "bodenrichtwerte": [{"lage": "...", "eur_qm": int, "hinweis": "..."}],
  "lage_eur_qm_stadtteil": [{"stadtteil": "...", "eur_qm_avg": int, "wohnlage_klasse": "..."}],
  "konfidenz_pro_tabelle": {"quelldokument": 0.0, "mfh_einkauf_baujahr": 0.0, "etw_exit_baujahr": 0.0, "bodenrichtwerte": 0.0, "lage_eur_qm_stadtteil": 0.0}
}"""
    return """{
  "quelldokument": {"titel": "...", "stand": "YYYY-MM-DD"},
  "basis_eur_qm_baujahr": [{"baujahr": "vor 1949|1949-1977|...", "eur_qm": float, "spanne_min": float, "spanne_max": float}],
  "lage_korrekturen": [{"klasse": "...", "korrektur_prozent": float, "beispielstrassen": ["..."]}],
  "ausstattungs_zuschlaege": [{"ausstattung": "...", "zuschlag_eur_qm": float}],
  "kappungsgrenze_prozent": 15 | 20 | null,
  "mietpreisbremse": true | false,
  "mietspiegel_typ": "qualifiziert" | "einfach" | "keiner",
  "konfidenz_pro_tabelle": {"basis_eur_qm_baujahr": 0.0, "lage_korrekturen": 0.0}
}"""
