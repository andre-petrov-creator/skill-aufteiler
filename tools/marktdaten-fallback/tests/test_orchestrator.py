import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from orchestrator import run_fallback


def test_run_gmb_konfidenz_passed_returns_value():
    find_mock = {
        "pdf_url": "https://boris.nrw.de/x.pdf",
        "notion_page_id": None,
        "quellen_trail": [
            {"typ": "notion", "quelle": "x", "ergebnis": "kein Treffer", "bonus": 0},
            {"typ": "boris-nrw", "quelle": "https://boris.nrw.de/x.pdf", "ergebnis": "PDF gefunden", "bonus": 30},
            {"typ": "stadt-webseite", "quelle": "https://bochum.de/x.pdf", "ergebnis": "Bestätigt", "bonus": 25},
            {"typ": "websearch", "quelle": "https://bochum.de/x.pdf", "ergebnis": "Bestätigt", "bonus": 20},
        ]
    }
    extract_mock = {
        "eur_per_qm": 1730.0,
        "zusatzfelder": {},
        "konfidenz_score": 90,
        "raw": {"quelldokument": {"titel": "GMB Bochum 2025"}, "etw_exit_baujahr": [{"baujahr": "1950-1959", "eur_qm_avg": 1730}]}
    }
    with patch("orchestrator.find.find_gmb_source", return_value=find_mock), \
         patch("orchestrator.download.cache_path_for", return_value=Path("/tmp/bochum-gmb-2025.pdf")), \
         patch("orchestrator.download.cache_hit", return_value=False), \
         patch("orchestrator.download.download_pdf"), \
         patch("orchestrator.extract.extract_gmb", return_value=extract_mock), \
         patch("orchestrator._notion_upload_gmb_page", return_value="new-page-id"):
        result = run_fallback(
            mode="gmb",
            stadt="Bochum",
            stadtteil="Eppendorf",
            baujahr=1955,
            interaktiv=False,
            slug="welperstr-39-hattingen",
        )

    assert result["ergebnis"]["eur_per_qm"] == 1730.0
    assert result["konfidenz_score"] >= 70
    assert result["notion_target_id"] == "new-page-id"
    assert result["fail_reason"] is None


def test_run_gmb_konfidenz_below_70_returns_null_in_akquise_mode():
    find_mock = {
        "pdf_url": None,
        "notion_page_id": None,
        "quellen_trail": [
            {"typ": "notion", "quelle": "x", "ergebnis": "kein Treffer", "bonus": 0},
            {"typ": "boris-nrw", "quelle": "x", "ergebnis": "Timeout", "bonus": 0},
            {"typ": "fail", "quelle": "kaskade", "ergebnis": "Alle Quellen erschöpft", "bonus": 0},
        ]
    }
    with patch("orchestrator.find.find_gmb_source", return_value=find_mock):
        result = run_fallback(
            mode="gmb",
            stadt="Kleinkleckersdorf",
            stadtteil=None,
            baujahr=1965,
            interaktiv=False,
            slug="test-slug",
        )

    assert result["ergebnis"]["eur_per_qm"] is None
    assert result["konfidenz_score"] == 0
    assert result["fail_reason"] is not None
    assert "Alle Quellen" in result["fail_reason"] or "konfidenz" in result["fail_reason"].lower()


def test_run_mietspiegel_passes_zusatzfelder():
    find_mock = {
        "pdf_url": "https://hagen.de/mietspiegel.pdf",
        "notion_db_row_id": None,
        "quellen_trail": [
            {"typ": "notion", "quelle": "x", "ergebnis": "kein Treffer", "bonus": 0},
            {"typ": "stadt-webseite", "quelle": "https://hagen.de/mietspiegel.pdf", "ergebnis": "ok", "bonus": 30},
            {"typ": "websearch", "quelle": "https://hagen.de/mietspiegel.pdf", "ergebnis": "Bestätigt", "bonus": 20},
            {"typ": "websearch", "quelle": "https://hagen.de/sonstige.pdf", "ergebnis": "Weiterer Treffer", "bonus": 20},
        ]
    }
    extract_mock = {
        "eur_per_qm": 6.20,
        "zusatzfelder": {"kappungsgrenze_prozent": 15, "mietpreisbremse": False, "mietspiegel_typ": "qualifiziert"},
        "konfidenz_score": 90,
        "raw": {"quelldokument": {"titel": "Hagen Mietspiegel"}}
    }
    with patch("orchestrator.find.find_mietspiegel_source", return_value=find_mock), \
         patch("orchestrator.download.cache_path_for", return_value=Path("/tmp/hagen-mietspiegel-2024.pdf")), \
         patch("orchestrator.download.cache_hit", return_value=False), \
         patch("orchestrator.download.download_pdf"), \
         patch("orchestrator.extract.extract_mietspiegel", return_value=extract_mock), \
         patch("orchestrator._notion_upsert_mietspiegel_row", return_value="new-row-id"):
        result = run_fallback(
            mode="mietspiegel",
            stadt="Hagen",
            stadtteil=None,
            baujahr=1965,
            interaktiv=True,
            slug="any-slug",
        )

    assert result["ergebnis"]["eur_per_qm"] == 6.20
    assert result["ergebnis"]["zusatzfelder"]["kappungsgrenze_prozent"] == 15
    assert result["ergebnis"]["zusatzfelder"]["mietpreisbremse"] is False
    assert result["notion_target_id"] == "new-row-id"
