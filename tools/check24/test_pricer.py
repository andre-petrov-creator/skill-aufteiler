"""Tests für den CHECK24 Pricer.

Reine Unit-Tests (Parser, Berechnungen) — kein Browser. Smoke-Test gegen
echtes CHECK24 ist mit @pytest.mark.slow markiert und läuft nur manuell.

    pytest                  # alle non-slow Tests
    pytest -m slow          # nur Smoke-Test
"""
from __future__ import annotations

import pytest

from form_steps import _parse_marktwert_block, _parse_trends
from generalisierter_datensatz import (
    GeneralisierterDatensatz,
    avg_int,
    avg_zimmer,
    from_lists,
    from_summary,
    round_half_up,
)


def test_parse_marktwert_block_real_check24_format():
    text = "Marktwertermittlung\nMarktwert\n173.800 €\nMarktwertspanne\n160.500 - 201.600 €"
    out = _parse_marktwert_block(text)
    assert out["mittel"] == 173_800
    assert out["min"] == 160_500
    assert out["max"] == 201_600


def test_parse_marktwert_block_with_pipes():
    text = "Marktwert | 173.800 € | Marktwertspanne | 160.500 - 201.600 €"
    out = _parse_marktwert_block(text)
    assert out["mittel"] == 173_800
    assert out["min"] == 160_500
    assert out["max"] == 201_600


def test_parse_marktwert_block_empty():
    assert _parse_marktwert_block("kein Wert hier") == {"min": None, "max": None, "mittel": None}


def test_parse_trends_alle_drei():
    text = (
        "Zeitverlauf | + | 6,65 % | (+10,8K €) | In den letzten 3 Jahren | "
        "3,84 % | (+6,4K €) | Seit letztem Jahr | "
        "3,52 % | (+6,1K €) | Prognose für das nächste Jahr | 200m | Verkaufspreis"
    )
    out = _parse_trends(text)
    assert out["jahre_3"] == 6.65
    assert out["jahr_1"] == 3.84
    assert out["prognose"] == 3.52


def test_parse_trends_negativ():
    text = (
        "- 2,5 % (-3K €) In den letzten 3 Jahren "
        "- 1,0 % (-1K €) Seit letztem Jahr "
        "+ 0,5 % (+0,5K €) Prognose für das nächste Jahr | 200m"
    )
    out = _parse_trends(text)
    assert out["jahre_3"] == -2.5
    assert out["jahr_1"] == -1.0
    assert out["prognose"] == 0.5


def test_round_half_up_at_boundary():
    assert round_half_up(2.5) == 3
    assert round_half_up(2.4999) == 2
    assert round_half_up(-2.5) == -2


def test_avg_zimmer_min_one():
    assert avg_zimmer([0.4, 0.4]) == 1


def test_from_summary_typical_mfh():
    d = from_summary(
        strasse="Prosperstr.", hausnr="59", plz="45356", ort="Essen",
        baujahr=1977, zustand="gut", ausstattung="normal",
        anzahl_we=6, gesamtwohnflaeche_qm=480, gesamtzimmer=18,
        anzahl_garagen=4, anzahl_aussenstellplaetze=2,
    )
    assert d.avg_wohnflaeche_qm == 80
    assert d.avg_zimmer == 3
    assert d.avg_badezimmer == 1
    assert d.hat_garage is True  # 4/6 = 0.67 >= 0.5
    assert d.hat_aussenstellplatz is False  # 2/6 = 0.33 < 0.5


def test_from_lists_with_uneven_sizes():
    d = from_lists(
        strasse="X", hausnr="1", plz="10115", ort="Berlin",
        baujahr=1990, zustand="neu", ausstattung="gehoben",
        wohnflaechen_qm=[55.0, 70.0, 92.0, 110.0],
        zimmer_liste=[2, 3, 4, 4],
        anzahl_garagen=2, anzahl_aussenstellplaetze=0,
    )
    assert d.avg_wohnflaeche_qm == avg_int([55.0, 70.0, 92.0, 110.0])
    assert d.avg_zimmer == 3
    assert d.hat_garage is True  # 2/4 = 0.5
    assert d.hat_aussenstellplatz is False


def test_garage_50_percent_boundary():
    d = from_summary(
        strasse="X", hausnr="1", plz="10115", ort="B",
        baujahr=2000, zustand="gut", ausstattung="normal",
        anzahl_we=10, gesamtwohnflaeche_qm=800, gesamtzimmer=30,
        anzahl_garagen=5, anzahl_aussenstellplaetze=4,
    )
    assert d.hat_garage is True
    assert d.hat_aussenstellplatz is False


def test_invalid_zustand_raises():
    with pytest.raises(ValueError, match="zustand"):
        GeneralisierterDatensatz(
            strasse="X", hausnr="1", plz="10115", ort="B",
            baujahr=2000, zustand="komisch", ausstattung="normal",
            anzahl_we=1, avg_wohnflaeche_qm=50, avg_zimmer=2,
        )


def test_list_length_mismatch_raises():
    with pytest.raises(ValueError, match="Listen-Längen"):
        from_lists(
            strasse="X", hausnr="1", plz="10115", ort="B",
            baujahr=1990, zustand="gut", ausstattung="normal",
            wohnflaechen_qm=[60.0, 70.0],
            zimmer_liste=[2],
        )


@pytest.mark.slow
def test_live_smoke():
    """Echter Browser-Lauf gegen CHECK24."""
    from form_steps import RunConfig, run

    d = from_summary(
        strasse="Kurfürstendamm", hausnr="21", plz="10719", ort="Berlin",
        baujahr=1985, zustand="gut", ausstattung="normal",
        anzahl_we=6, gesamtwohnflaeche_qm=480, gesamtzimmer=18,
        anzahl_garagen=4, anzahl_aussenstellplaetze=2,
    )
    result = run(d, RunConfig(headless=False, kaufabsicht="kauf", verbose=False))
    assert result["status"] == "ok", f"Lauf fehlgeschlagen: {result}"
    assert result["marktwert_eur_mittel"] and result["marktwert_eur_mittel"] > 50_000
