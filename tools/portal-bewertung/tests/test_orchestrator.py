# -*- coding: utf-8 -*-
"""Unit-Tests fuer den Portal-Orchestrator (Step 15 + Modul-0-v2)."""
from __future__ import annotations

import sys
from pathlib import Path

# Make project root importable
THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

import pytest

from core.datensatz import from_lists, from_summary
from orchestrator import (
    _avg_wohnflaeche_pro_we,
    _compute_eur_per_qm,
    _compute_konsens,
    _extract_immometrica_eur_per_qm,
    _gesamtwohnflaeche,
)


# -----------------------------------------------------------------------------
# _avg_wohnflaeche_pro_we
# -----------------------------------------------------------------------------

def test_avg_wohnflaeche_from_summary():
    d = from_summary(
        strasse="X", hausnr="1", plz="45357", ort="Essen",
        baujahr=1965, zustand="gut", ausstattung="normal",
        anzahl_we=4, gesamtwohnflaeche_qm=300.0, gesamtzimmer=12.0,
    )
    # from_summary setzt avg_wohnflaeche_qm = gesamt / anzahl = 75
    assert _avg_wohnflaeche_pro_we(d) == 75.0


def test_avg_wohnflaeche_from_lists():
    d = from_lists(
        strasse="X", hausnr="1", plz="45357", ort="Essen",
        baujahr=1965, zustand="gut", ausstattung="normal",
        wohnflaechen_qm=[65, 70, 75, 80],
        zimmer_liste=[2, 3, 3, 3],
        badezimmer_liste=[1, 1, 1, 1],
    )
    # avg = (65+70+75+80)/4 = 72.5 — gerundet zu 73 in from_lists
    val = _avg_wohnflaeche_pro_we(d)
    assert val is not None
    assert 72 <= val <= 74


# -----------------------------------------------------------------------------
# _gesamtwohnflaeche
# -----------------------------------------------------------------------------

def test_gesamtwohnflaeche_fallback_from_avg_and_n():
    d = from_lists(
        strasse="X", hausnr="1", plz="45357", ort="Essen",
        baujahr=1965, zustand="gut", ausstattung="normal",
        wohnflaechen_qm=[60, 70, 80, 90],
        zimmer_liste=[2, 3, 3, 3],
        badezimmer_liste=[1, 1, 1, 1],
    )
    # from_lists setzt avg_wohnflaeche_qm = 75, anzahl_we = 4 → 300
    val = _gesamtwohnflaeche(d)
    assert val == 300.0


# -----------------------------------------------------------------------------
# _compute_eur_per_qm
# -----------------------------------------------------------------------------

def test_compute_eur_per_qm_from_extra_homeday():
    portal_out = {"status": "ok", "marktwert_eur_mittel": None, "extra": {"eur_per_qm": 2200}}
    assert _compute_eur_per_qm(portal_out, 73) == 2200.0


def test_compute_eur_per_qm_from_marktwert():
    portal_out = {"status": "ok", "marktwert_eur_mittel": 130_000}
    val = _compute_eur_per_qm(portal_out, 73)
    assert val is not None
    assert 1770 < val < 1790  # 130000/73 ≈ 1781


def test_compute_eur_per_qm_error_status_returns_none():
    portal_out = {"status": "error", "marktwert_eur_mittel": 100_000}
    assert _compute_eur_per_qm(portal_out, 50) is None


def test_compute_eur_per_qm_no_wohnflaeche_no_extra_returns_none():
    portal_out = {"status": "ok", "marktwert_eur_mittel": 100_000}
    assert _compute_eur_per_qm(portal_out, None) is None


def test_compute_eur_per_qm_prefers_extra_over_marktwert():
    # Wenn beide Felder vorhanden, gewinnt extra.eur_per_qm
    portal_out = {
        "status": "ok",
        "marktwert_eur_mittel": 100_000,
        "extra": {"eur_per_qm": 2500},
    }
    assert _compute_eur_per_qm(portal_out, 50) == 2500.0


# -----------------------------------------------------------------------------
# _extract_immometrica_eur_per_qm
# -----------------------------------------------------------------------------

def test_extract_immometrica_eur_per_qm_returns_plz_etw():
    immo = {"extra": {
        "plz_etw":   {"uebersicht": {"median_preis_eur_per_qm": 2382}},
        "stadt_etw": {"uebersicht": {"median_preis_eur_per_qm": 2252}},
    }}
    assert _extract_immometrica_eur_per_qm(immo) == 2382.0


def test_extract_immometrica_eur_per_qm_missing_slots():
    assert _extract_immometrica_eur_per_qm({"extra": {}}) is None


def test_extract_immometrica_eur_per_qm_invalid_input():
    assert _extract_immometrica_eur_per_qm(None) is None


# -----------------------------------------------------------------------------
# _compute_konsens
# -----------------------------------------------------------------------------

def test_compute_konsens_empty():
    out = _compute_konsens([])
    assert out["konsens_median_eur"] is None
    assert out["anzahl_quellen"] == 0


def test_compute_konsens_single_value():
    out = _compute_konsens([130_000])
    assert out["konsens_median_eur"] == 130_000
    assert out["konsens_spread_eur"] == 0
    assert out["anzahl_quellen"] == 1


def test_compute_konsens_three_values():
    out = _compute_konsens([100_000, 150_000, 200_000])
    assert out["konsens_median_eur"] == 150_000
    assert out["konsens_spread_eur"] == 100_000
    assert out["konsens_spread_prozent"] == pytest.approx(66.7, abs=0.1)
    assert out["anzahl_quellen"] == 3


def test_compute_konsens_filters_zero_and_none():
    out = _compute_konsens([100_000, 0, None, 200_000])
    assert out["anzahl_quellen"] == 2
    assert out["konsens_median_eur"] == 150_000
