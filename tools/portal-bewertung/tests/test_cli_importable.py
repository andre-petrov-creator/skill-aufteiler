"""Smoke-Test für CLI-Entry m00_portal_pricer.py.

Live-CLI-Run muss vom User mit echtem Browser ausgeführt werden — siehe
docs/cli.md für Beispielaufrufe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))


def test_cli_module_imports() -> None:
    import m00_portal_pricer

    assert hasattr(m00_portal_pricer, "main")
    assert "check24" in m00_portal_pricer.PORTAL_REGISTRY


def test_cli_rejects_unknown_portal() -> None:
    import m00_portal_pricer

    with pytest.raises(SystemExit):
        m00_portal_pricer._parse_args(["--portal", "myspace"])


def test_cli_summary_mode_requires_strasse() -> None:
    """Ohne Pflicht-Args (oder --datensatz) muss CLI mit SystemExit abbrechen."""
    import m00_portal_pricer

    args = m00_portal_pricer._parse_args(["--portal", "check24"])
    with pytest.raises(SystemExit):
        m00_portal_pricer._build_datensatz_from_args(args)


def test_cli_summary_mode_builds_datensatz() -> None:
    import m00_portal_pricer

    args = m00_portal_pricer._parse_args(
        [
            "--portal", "check24",
            "--strasse", "Prosperstr.",
            "--hausnr", "59",
            "--plz", "45357",
            "--ort", "Essen",
            "--baujahr", "1965",
            "--zustand", "gut",
            "--ausstattung", "normal",
            "--anzahl-we", "4",
            "--gesamtwohnflaeche-qm", "320",
            "--gesamtzimmer", "12",
            "--anzahl-garagen", "2",
        ]
    )
    d = m00_portal_pricer._build_datensatz_from_args(args)
    assert d.strasse == "Prosperstr."
    assert d.avg_wohnflaeche_qm == 80
    assert d.avg_zimmer == 3
    assert d.hat_garage is True


def test_cli_lists_mode_builds_datensatz() -> None:
    import m00_portal_pricer

    args = m00_portal_pricer._parse_args(
        [
            "--portal", "check24",
            "--strasse", "Prosperstr.",
            "--hausnr", "59",
            "--plz", "45357",
            "--ort", "Essen",
            "--baujahr", "1965",
            "--zustand", "gut",
            "--ausstattung", "normal",
            "--anzahl-we", "4",
            "--wohnflaechen-qm", "60,70,80,90",
            "--zimmer-liste", "2,3,3,4",
            "--badezimmer-liste", "1,1,1,2",
        ]
    )
    d = m00_portal_pricer._build_datensatz_from_args(args)
    assert d.avg_wohnflaeche_qm == 75
    assert d.avg_zimmer == 3


def test_cli_lists_mode_rejects_mismatched_length() -> None:
    import m00_portal_pricer

    args = m00_portal_pricer._parse_args(
        [
            "--portal", "check24",
            "--strasse", "X", "--hausnr", "1", "--plz", "00000", "--ort", "Y",
            "--baujahr", "2000", "--zustand", "gut", "--ausstattung", "normal",
            "--anzahl-we", "4",
            "--wohnflaechen-qm", "60,70",
            "--zimmer-liste", "2,3",
        ]
    )
    with pytest.raises(SystemExit):
        m00_portal_pricer._build_datensatz_from_args(args)
