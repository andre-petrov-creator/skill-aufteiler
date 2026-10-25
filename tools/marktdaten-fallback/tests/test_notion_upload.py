from unittest.mock import patch, MagicMock

from notion_upload import build_gmb_page_body, build_mietspiegel_row_payload


def test_build_gmb_page_body_contains_pflichtsections():
    raw = {
        "quelldokument": {
            "titel": "Grundstücksmarktbericht Bochum 2025",
            "autor": "Gutachterausschuss Bochum",
            "erschienen": "Mai 2025",
            "datenbasis": "2055 Kauffälle 2024"
        },
        "mfh_einkauf_baujahr": [
            {"baujahr": "1950-1974", "n_2024": 92, "qm_wfl_avg": 422, "eur_qm_avg": 1280, "eur_qm_min": 670, "eur_qm_max": 1960, "s": 290}
        ],
        "etw_exit_baujahr": [
            {"baujahr": "1950-1959", "n_2024": 125, "qm_wfl_avg": 61, "eur_qm_avg": 1730, "eur_qm_min": 540, "eur_qm_max": 3060}
        ],
    }
    body = build_gmb_page_body(
        raw=raw,
        stadt="Bochum",
        stadtteil="Eppendorf",
        baujahr=1955,
        konfidenz_score=85,
        pdf_url="https://boris.nrw.de/x.pdf",
        anfrage_adresse="Welperstraße 39, 45525 Hattingen",
        gelieferter_wert=1730,
    )
    assert "# Quelldokument" in body
    assert "# MFH-Einkaufspreise" in body
    assert "# ETW-Verkaufspreise" in body
    assert "# Auto-Fallback-Metadaten" in body
    assert "1730" in body  # gelieferter Wert
    assert "Bochum" in body
    assert "Konfidenz: 85" in body


def test_build_mietspiegel_row_payload_maps_to_db_schema():
    raw = {
        "quelldokument": {"titel": "Mietspiegel Hagen 2024", "stand": "2024-05-01"},
        "kappungsgrenze_prozent": 20,
        "mietpreisbremse": False,
        "mietspiegel_typ": "qualifiziert",
    }
    payload = build_mietspiegel_row_payload(
        raw=raw,
        stadt="Hagen",
        pdf_url="https://hagen.de/mietspiegel.pdf",
        vollstaendigkeit="komplett",
    )
    assert payload["Stadt"] == "Hagen"
    assert payload["Kappungsgrenze"] == "20%"
    assert payload["Mietpreisbremse"] is False
    assert payload["Mietspiegel-Typ"] == "qualifiziert"
    assert payload["Quelle PDF"] == "https://hagen.de/mietspiegel.pdf"
    assert payload["Vollstaendigkeit"] == "komplett"


def test_build_mietspiegel_row_payload_kappung_15():
    raw = {"quelldokument": {"titel": "x", "stand": "2024-01-01"}, "kappungsgrenze_prozent": 15}
    payload = build_mietspiegel_row_payload(raw=raw, stadt="Essen", pdf_url="https://essen.de/x.pdf",
                                            vollstaendigkeit="unvollstaendig")
    assert payload["Kappungsgrenze"] == "15%"


def test_build_mietspiegel_row_payload_keiner_typ():
    raw = {"quelldokument": {"titel": "x", "stand": "2024-01-01"}, "mietspiegel_typ": "keiner"}
    payload = build_mietspiegel_row_payload(raw=raw, stadt="Kleinstadt", pdf_url="https://kleinstadt.de/x.pdf",
                                            vollstaendigkeit="fehlt")
    assert payload["Mietspiegel-Typ"] == "keiner"
    assert payload["Vollstaendigkeit"] == "fehlt"
