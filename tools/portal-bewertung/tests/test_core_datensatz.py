"""Unit-Tests für core/datensatz.py — GeneralisierterDatensatz + Factories."""
from __future__ import annotations

import pytest

from core.datensatz import (
    AUSSTATTUNG_VALUES,
    ZUSTAND_VALUES,
    GeneralisierterDatensatz,
    avg_zimmer,
    from_lists,
    from_summary,
    round_half_up,
)


def test_round_half_up_below_half_rounds_down() -> None:
    assert round_half_up(1.4) == 1


def test_round_half_up_exact_half_rounds_up() -> None:
    assert round_half_up(2.5) == 3


def test_round_half_up_negative_half_rounds_toward_zero() -> None:
    # math.floor(-1.5 + 0.5) = math.floor(-1.0) = -1
    assert round_half_up(-1.5) == -1


def test_avg_zimmer_returns_min_one_for_small_avg() -> None:
    assert avg_zimmer([0.5, 0.5]) == 1


def test_avg_zimmer_rounds_half_up() -> None:
    # (2 + 3 + 3) / 3 = 2.666... → 3
    assert avg_zimmer([2.0, 3.0, 3.0]) == 3


def test_avg_zimmer_raises_on_empty_list() -> None:
    with pytest.raises(ValueError):
        avg_zimmer([])


def test_from_summary_computes_averages_and_garage_flag() -> None:
    d = from_summary(
        strasse="Prosperstr.",
        hausnr="59",
        plz="45357",
        ort="Essen",
        baujahr=1965,
        zustand="gut",
        ausstattung="normal",
        anzahl_we=4,
        gesamtwohnflaeche_qm=320.0,
        gesamtzimmer=12.0,
        anzahl_garagen=2,
        anzahl_aussenstellplaetze=1,
    )
    assert d.avg_wohnflaeche_qm == 80
    assert d.avg_zimmer == 3
    assert d.avg_badezimmer == 1
    assert d.hat_garage is True
    assert d.hat_aussenstellplatz is False
    assert d.anzahl_we == 4


def test_from_summary_raises_on_zero_we() -> None:
    with pytest.raises(ValueError):
        from_summary(
            strasse="X",
            hausnr="1",
            plz="00000",
            ort="Y",
            baujahr=2000,
            zustand="gut",
            ausstattung="normal",
            anzahl_we=0,
            gesamtwohnflaeche_qm=100.0,
            gesamtzimmer=3.0,
        )


def test_from_lists_computes_averages_from_we_lists() -> None:
    d = from_lists(
        strasse="Prosperstr.",
        hausnr="59",
        plz="45357",
        ort="Essen",
        baujahr=1965,
        zustand="gut",
        ausstattung="normal",
        wohnflaechen_qm=[60.0, 70.0, 80.0, 90.0],
        zimmer_liste=[2.0, 3.0, 3.0, 4.0],
        badezimmer_liste=[1, 1, 1, 2],
        anzahl_garagen=2,
        anzahl_aussenstellplaetze=4,
    )
    assert d.anzahl_we == 4
    assert d.avg_wohnflaeche_qm == 75
    assert d.avg_zimmer == 3
    assert d.avg_badezimmer == 1
    assert d.hat_garage is True
    assert d.hat_aussenstellplatz is True


def test_garage_50_percent_below_threshold_is_false() -> None:
    d = from_summary(
        strasse="X",
        hausnr="1",
        plz="00000",
        ort="Y",
        baujahr=2000,
        zustand="gut",
        ausstattung="normal",
        anzahl_we=3,
        gesamtwohnflaeche_qm=240.0,
        gesamtzimmer=9.0,
        anzahl_garagen=1,
    )
    # 1/3 = 0.33 < 0.5 → False
    assert d.hat_garage is False


def test_invalid_zustand_raises() -> None:
    with pytest.raises(ValueError, match="zustand"):
        GeneralisierterDatensatz(
            strasse="X",
            hausnr="1",
            plz="00000",
            ort="Y",
            baujahr=2000,
            zustand="modern",
            ausstattung="normal",
            anzahl_we=1,
            avg_wohnflaeche_qm=80,
            avg_zimmer=3,
        )


def test_invalid_ausstattung_raises() -> None:
    with pytest.raises(ValueError, match="ausstattung"):
        GeneralisierterDatensatz(
            strasse="X",
            hausnr="1",
            plz="00000",
            ort="Y",
            baujahr=2000,
            zustand="gut",
            ausstattung="protzig",
            anzahl_we=1,
            avg_wohnflaeche_qm=80,
            avg_zimmer=3,
        )


def test_list_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="Listen-Längen"):
        from_lists(
            strasse="X",
            hausnr="1",
            plz="00000",
            ort="Y",
            baujahr=2000,
            zustand="gut",
            ausstattung="normal",
            wohnflaechen_qm=[60.0, 70.0],
            zimmer_liste=[2.0, 3.0, 3.0],
        )


def test_constants_exported() -> None:
    assert "gut" in ZUSTAND_VALUES
    assert "normal" in AUSSTATTUNG_VALUES
