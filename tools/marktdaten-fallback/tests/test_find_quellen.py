from unittest.mock import patch, MagicMock

from find import find_gmb_source, find_mietspiegel_source


def test_gmb_notion_treffer_dominates():
    """Wenn Notion-Page mit passendem Stadt/Stadtteil/Baujahr existiert, weiter Stufen werden NICHT aufgerufen."""
    notion_mock = MagicMock(return_value={
        "found": True,
        "page_id": "abc-123",
        "stadtteil_match": True,
        "baujahr_match": True
    })
    with patch("find._notion_search_gmb", notion_mock), \
         patch("find._fetch_boris_gmb_index") as boris_mock:
        result = find_gmb_source(stadt="Bochum", stadtteil="Eppendorf", baujahr=1965)

    assert result["pdf_url"] is None  # Notion-Treffer → kein neuer Download nötig
    assert result["notion_page_id"] == "abc-123"
    assert result["quellen_trail"][0]["typ"] == "notion"
    assert result["quellen_trail"][0]["bonus"] == 60
    boris_mock.assert_not_called()


def test_gmb_kaskade_faellt_durch_zu_boris():
    """Wenn Notion-Page nicht vorhanden, BORIS NRW + Stadt-Webseite werden gefragt."""
    with patch("find._notion_search_gmb", return_value={"found": False}), \
         patch("find._fetch_boris_gmb_index", return_value={
             "pdf_url": "https://boris.nrw.de/borisplus/dokumente/gmb-bochum-2025.pdf",
             "ergebnis": "PDF-Link gefunden"
         }):
        result = find_gmb_source(stadt="Bochum", stadtteil=None, baujahr=1960)

    typen = [e["typ"] for e in result["quellen_trail"]]
    assert "notion" in typen
    assert "boris-nrw" in typen
    assert result["pdf_url"] == "https://boris.nrw.de/borisplus/dokumente/gmb-bochum-2025.pdf"


def test_gmb_off_whitelist_url_wird_rejected():
    """Wenn eine Quelle eine Off-Whitelist-URL liefert, wird sie hart abgelehnt (typ=fail)."""
    with patch("find._notion_search_gmb", return_value={"found": False}), \
         patch("find._fetch_boris_gmb_index", return_value={
             "pdf_url": "https://immowelt.de/gmb-bochum.pdf",  # nicht offiziell
             "ergebnis": "Treffer aus BORIS-Index"
         }):
        result = find_gmb_source(stadt="Bochum", stadtteil=None, baujahr=1960)

    fail_eintraege = [e for e in result["quellen_trail"] if e["typ"] == "fail"]
    assert len(fail_eintraege) >= 1
    assert "Off-Whitelist" in fail_eintraege[0]["ergebnis"]
    assert result["pdf_url"] is None or result["pdf_url"] != "https://immowelt.de/gmb-bochum.pdf"


def test_mietspiegel_known_stadt_uses_hardcoded_url():
    with patch("find._notion_db_lookup_mietspiegel", return_value={"found": False}), \
         patch("find._fetch_stadt_mietspiegel_page", return_value={
             "pdf_url": "https://www.bochum.de/Wohnen-und-Bauen/Mietspiegel/mietspiegel-2024.pdf",
             "ergebnis": "PDF aus Stadt-Webseite extrahiert"
         }):
        result = find_mietspiegel_source(stadt="Bochum")

    typen = [e["typ"] for e in result["quellen_trail"]]
    assert "stadt-webseite" in typen
    assert result["pdf_url"].endswith(".pdf")


def test_mietspiegel_unbekannte_stadt_geht_websearch():
    # Offizielle Domain aus der Whitelist simuliert WebSearch-Fund einer unbekannten Stadt
    with patch("find._notion_db_lookup_mietspiegel", return_value={"found": False}), \
         patch("find._fetch_stadt_mietspiegel_page", return_value=None), \
         patch("find._websearch_mietspiegel", return_value={
             "pdf_url": "https://www.hagen.de/mietspiegel-2024.pdf",
             "ergebnis": "WebSearch-Treffer site-restricted"
         }) as ws_mock:
        result = find_mietspiegel_source(stadt="Kleinstadt")

    ws_mock.assert_called_once()
    assert result["pdf_url"] is not None
