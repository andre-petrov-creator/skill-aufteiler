"""FIND-Phase: Quellen-Kaskade gegen offizielle Whitelist."""

from typing import Optional, Dict, Any, List

from config import (
    is_whitelisted_url,
    get_stadt_mietspiegel_url,
    get_boris_index_url,
)


def find_gmb_source(stadt: str, stadtteil: Optional[str], baujahr: Optional[int]) -> Dict[str, Any]:
    """Quellen-Kaskade Modus 'gmb'. Returnt {pdf_url, notion_page_id, quellen_trail}.

    Reihenfolge: notion → boris-nrw → stadt-webseite → geoportal → websearch.
    Erste erfolgreiche Stufe stoppt die Kaskade — außer bei notion+treffer wird kein
    pdf_url gesetzt (Notion-Treffer bedeutet: Werte sind schon in Notion, kein neuer Download).
    """
    trail: List[Dict[str, Any]] = []

    # 1. Notion-Page-Suche
    notion_res = _notion_search_gmb(stadt, stadtteil, baujahr)
    if notion_res.get("found"):
        trail.append({
            "typ": "notion",
            "quelle": notion_res["page_id"],
            "ergebnis": f"Sub-Page für {stadt} GMB gefunden, Stadtteil-Match={notion_res.get('stadtteil_match')}",
            "bonus": 60
        })
        return {
            "pdf_url": None,
            "notion_page_id": notion_res["page_id"],
            "quellen_trail": trail
        }
    trail.append({"typ": "notion", "quelle": "Preisdatenbank", "ergebnis": "kein Treffer", "bonus": 0})

    # 2. BORIS NRW
    boris_res = _fetch_boris_gmb_index(stadt, baujahr)
    if boris_res and boris_res.get("pdf_url"):
        pdf_url = boris_res["pdf_url"]
        if is_whitelisted_url(pdf_url):
            trail.append({
                "typ": "boris-nrw",
                "quelle": pdf_url,
                "ergebnis": boris_res["ergebnis"],
                "bonus": 30
            })
            return {"pdf_url": pdf_url, "notion_page_id": None, "quellen_trail": trail}
        trail.append({"typ": "fail", "quelle": pdf_url, "ergebnis": "Off-Whitelist (BORIS-Treffer)", "bonus": 0})

    # 3. Stadt-Webseite
    stadt_res = _fetch_stadt_gutachterausschuss_page(stadt)
    if stadt_res and stadt_res.get("pdf_url"):
        pdf_url = stadt_res["pdf_url"]
        if is_whitelisted_url(pdf_url):
            trail.append({
                "typ": "stadt-webseite",
                "quelle": pdf_url,
                "ergebnis": stadt_res["ergebnis"],
                "bonus": 25
            })
            return {"pdf_url": pdf_url, "notion_page_id": None, "quellen_trail": trail}
        trail.append({"typ": "fail", "quelle": pdf_url, "ergebnis": "Off-Whitelist (Stadt-Treffer)", "bonus": 0})

    # 4. Geoportal NRW
    geo_res = _fetch_geoportal_nrw(stadt)
    if geo_res and geo_res.get("pdf_url"):
        pdf_url = geo_res["pdf_url"]
        if is_whitelisted_url(pdf_url):
            trail.append({
                "typ": "geoportal",
                "quelle": pdf_url,
                "ergebnis": geo_res["ergebnis"],
                "bonus": 20
            })
            return {"pdf_url": pdf_url, "notion_page_id": None, "quellen_trail": trail}

    # 5. site-restricted WebSearch (letzte Stufe)
    ws_res = _websearch_gmb(stadt, baujahr)
    if ws_res and ws_res.get("pdf_url") and is_whitelisted_url(ws_res["pdf_url"]):
        trail.append({
            "typ": "websearch",
            "quelle": ws_res["pdf_url"],
            "ergebnis": ws_res["ergebnis"],
            "bonus": 10
        })
        return {"pdf_url": ws_res["pdf_url"], "notion_page_id": None, "quellen_trail": trail}

    # Alle Quellen erschöpft
    trail.append({"typ": "fail", "quelle": "kaskade", "ergebnis": "Alle Quellen erschöpft, keine PDF-URL", "bonus": 0})
    return {"pdf_url": None, "notion_page_id": None, "quellen_trail": trail}


def find_mietspiegel_source(stadt: str) -> Dict[str, Any]:
    """Quellen-Kaskade Modus 'mietspiegel'. Reihenfolge: notion-db → stadt-webseite-hardcoded → site-websearch."""
    trail: List[Dict[str, Any]] = []

    # 1. Notion-DB-Stadt-Zeile
    notion_res = _notion_db_lookup_mietspiegel(stadt)
    if notion_res.get("found"):
        pdf_url = notion_res.get("pdf_url")
        if pdf_url and is_whitelisted_url(pdf_url):
            trail.append({
                "typ": "notion",
                "quelle": notion_res["row_id"],
                "ergebnis": f"DB-Zeile vorhanden mit PDF-URL: {pdf_url}",
                "bonus": 60
            })
            return {"pdf_url": pdf_url, "notion_db_row_id": notion_res["row_id"], "quellen_trail": trail}
    trail.append({"typ": "notion", "quelle": "Mietspiegel NRW", "ergebnis": "kein Treffer / PDF-URL fehlt", "bonus": 0})

    # 2. Stadt-Webseite (hardcoded URL aus config)
    stadt_url = get_stadt_mietspiegel_url(stadt)
    stadt_res = _fetch_stadt_mietspiegel_page(stadt_url) if stadt_url else None
    if stadt_res and stadt_res.get("pdf_url"):
        pdf_url = stadt_res["pdf_url"]
        if is_whitelisted_url(pdf_url):
            trail.append({
                "typ": "stadt-webseite",
                "quelle": pdf_url,
                "ergebnis": stadt_res["ergebnis"],
                "bonus": 30
            })
            return {"pdf_url": pdf_url, "notion_db_row_id": None, "quellen_trail": trail}

    # 3. site-restricted WebSearch
    ws_res = _websearch_mietspiegel(stadt)
    if ws_res and ws_res.get("pdf_url") and is_whitelisted_url(ws_res["pdf_url"]):
        trail.append({
            "typ": "websearch",
            "quelle": ws_res["pdf_url"],
            "ergebnis": ws_res["ergebnis"],
            "bonus": 20
        })
        return {"pdf_url": ws_res["pdf_url"], "notion_db_row_id": None, "quellen_trail": trail}

    trail.append({"typ": "fail", "quelle": "kaskade", "ergebnis": "Alle Mietspiegel-Quellen erschöpft", "bonus": 0})
    return {"pdf_url": None, "notion_db_row_id": None, "quellen_trail": trail}


# --- Quellen-Helper (Stubs — wirklich verbunden in Task 9 Orchestrator + via MCP-CLI) ---

def _notion_search_gmb(stadt: str, stadtteil: Optional[str], baujahr: Optional[int]) -> Dict[str, Any]:
    """Stub: in Tests gemockt. Live-Aufruf läuft über MCP-Notion-Tool (siehe orchestrator.py)."""
    return {"found": False}


def _notion_db_lookup_mietspiegel(stadt: str) -> Dict[str, Any]:
    return {"found": False}


def _fetch_boris_gmb_index(stadt: str, baujahr: Optional[int]) -> Optional[Dict[str, Any]]:
    return None


def _fetch_stadt_gutachterausschuss_page(stadt: str) -> Optional[Dict[str, Any]]:
    return None


def _fetch_stadt_mietspiegel_page(stadt_url: Optional[str]) -> Optional[Dict[str, Any]]:
    return None


def _fetch_geoportal_nrw(stadt: str) -> Optional[Dict[str, Any]]:
    return None


def _websearch_gmb(stadt: str, baujahr: Optional[int]) -> Optional[Dict[str, Any]]:
    return None


def _websearch_mietspiegel(stadt: str) -> Optional[Dict[str, Any]]:
    return None
