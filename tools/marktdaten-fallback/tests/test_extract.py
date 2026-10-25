from unittest.mock import patch
from pathlib import Path

from extract import extract_gmb, extract_mietspiegel


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_gmb_returns_schema_compliant_json():
    """LLM-Call gemockt. Test prüft Schema-Compliance der returned-Struktur."""
    mock_response = {
        "quelldokument": {
            "titel": "Grundstücksmarktbericht Bochum 2025",
            "autor": "Gutachterausschuss für Grundstückswerte Bochum",
            "erschienen": "Mai 2025",
            "datenbasis": "2055 Kauffälle 2024"
        },
        "mfh_einkauf_baujahr": [
            {"baujahr": "vor 1950", "n_2024": 69, "qm_wfl_avg": 390, "eur_qm_avg": 1020, "eur_qm_min": 340, "eur_qm_max": 1850, "s": 310},
            {"baujahr": "1950-1974", "n_2024": 92, "qm_wfl_avg": 422, "eur_qm_avg": 1280, "eur_qm_min": 670, "eur_qm_max": 1960, "s": 290}
        ],
        "etw_exit_baujahr": [
            {"baujahr": "1950-1974", "n_2024": 125, "qm_wfl_avg": 61, "eur_qm_avg": 1730, "eur_qm_min": 540, "eur_qm_max": 3060}
        ],
        "konfidenz_pro_tabelle": {"mfh_einkauf_baujahr": 0.95, "etw_exit_baujahr": 0.92, "quelldokument": 0.98}
    }
    pdf = FIXTURES / "bochum-gmb-2025-excerpt.pdf"
    with patch("extract._call_opus_extract", return_value=mock_response):
        result = extract_gmb(pdf_path=pdf, stadt="Bochum", stadtteil=None, baujahr=1965)

    assert result["eur_per_qm"] is not None
    assert isinstance(result["eur_per_qm"], (int, float))
    assert "quelldokument" in result["raw"]
    assert result["konfidenz_score"] >= 0


def test_extract_gmb_konfidenz_unter_06_setzt_wert_auf_none():
    mock_response = {
        "quelldokument": {"titel": "X"},
        "mfh_einkauf_baujahr": [],
        "etw_exit_baujahr": [],
        "konfidenz_pro_tabelle": {"etw_exit_baujahr": 0.4}  # niedrig
    }
    pdf = FIXTURES / "bochum-gmb-2025-excerpt.pdf"
    with patch("extract._call_opus_extract", return_value=mock_response):
        result = extract_gmb(pdf_path=pdf, stadt="Bochum", stadtteil="Eppendorf", baujahr=1965)

    # ETW-Tabelle hat Konfidenz < 0.6 → eur_per_qm sollte null sein
    assert result["eur_per_qm"] is None


def test_extract_mietspiegel_returns_kappung_and_basis():
    mock_response = {
        "quelldokument": {"titel": "Mietspiegel Essen 2024", "stand": "2024-04-01"},
        "basis_eur_qm_baujahr": [
            {"baujahr": "vor 1949", "eur_qm": 5.50, "spanne_min": 4.20, "spanne_max": 6.80},
            {"baujahr": "1949-1977", "eur_qm": 6.20, "spanne_min": 4.90, "spanne_max": 7.50}
        ],
        "kappungsgrenze_prozent": 15,
        "mietpreisbremse": True,
        "mietspiegel_typ": "qualifiziert",
        "konfidenz_pro_tabelle": {"basis_eur_qm_baujahr": 0.93}
    }
    pdf = FIXTURES / "essen-mietspiegel-2024-excerpt.pdf"
    with patch("extract._call_opus_extract", return_value=mock_response):
        result = extract_mietspiegel(pdf_path=pdf, stadt="Essen", baujahr=1965)

    assert result["eur_per_qm"] == 6.20  # 1949-1977 Klasse
    assert result["zusatzfelder"]["kappungsgrenze_prozent"] == 15
    assert result["zusatzfelder"]["mietpreisbremse"] is True
    assert result["zusatzfelder"]["mietspiegel_typ"] == "qualifiziert"
