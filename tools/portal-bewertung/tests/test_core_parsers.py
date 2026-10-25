"""Unit-Tests für core/parsers.py — portal-agnostische Regex-Parser."""
from __future__ import annotations

from core.parsers import (
    build_trend_label,
    parse_marktwert_block,
    parse_trends,
    trend_ampel,
)


def test_parse_marktwert_block_with_newlines() -> None:
    text = (
        "Marktwertermittlung\n"
        "Marktwert\n173.000 €\n"
        "Marktwertspanne\n168.000 - 178.000 €\n"
    )
    out = parse_marktwert_block(text)
    assert out == {"min": 168_000, "max": 178_000, "mittel": 173_000}


def test_parse_marktwert_block_with_pipes() -> None:
    text = (
        "Marktwertermittlung | Marktwert | 250.000 € | Marktwertspanne "
        "| 240.000 - 260.000 €"
    )
    out = parse_marktwert_block(text)
    assert out == {"min": 240_000, "max": 260_000, "mittel": 250_000}


def test_parse_marktwert_block_empty_returns_nones() -> None:
    out = parse_marktwert_block("Keine relevanten Daten")
    assert out == {"min": None, "max": None, "mittel": None}


def test_parse_trends_three_positive_values() -> None:
    text = (
        "Zeitverlauf "
        "+6,7 % (15.000) In den letzten 3 Jahren "
        "+3,0 % (5.000) Seit letztem Jahr "
        "+1,4 % (2.000) Prognose für das nächste Jahr"
    )
    out = parse_trends(text)
    assert out["jahre_3"] == 6.7
    assert out["jahr_1"] == 3.0
    assert out["prognose"] == 1.4


def test_parse_trends_with_negative_prognose() -> None:
    text = (
        "+2,0 % (1.000) In den letzten 3 Jahren "
        "-1,5 % (-500) Seit letztem Jahr "
        "-3,0 % (-1.200) Prognose für das nächste Jahr"
    )
    out = parse_trends(text)
    assert out["jahre_3"] == 2.0
    assert out["jahr_1"] == -1.5
    assert out["prognose"] == -3.0


def test_parse_trends_missing_label_stays_none() -> None:
    text = "+5,0 % In den letzten 3 Jahren"
    out = parse_trends(text)
    assert out["jahre_3"] == 5.0
    assert out["jahr_1"] is None
    assert out["prognose"] is None


def test_trend_ampel_gruen_for_positive_trends() -> None:
    trends = {"jahre_3": 6.7, "jahr_1": 3.0, "prognose": 1.4}
    ampel, label = trend_ampel(trends)
    assert ampel == "gruen"
    assert "steigend" in label


def test_trend_ampel_rot_when_prognose_negative() -> None:
    trends = {"jahre_3": 4.0, "jahr_1": 2.0, "prognose": -1.5}
    ampel, label = trend_ampel(trends)
    assert ampel == "rot"


def test_trend_ampel_rot_when_one_and_three_year_negative() -> None:
    trends = {"jahre_3": -2.0, "jahr_1": -1.0, "prognose": None}
    ampel, label = trend_ampel(trends)
    assert ampel == "rot"


def test_trend_ampel_gelb_for_stagnation() -> None:
    trends = {"jahre_3": 1.0, "jahr_1": 0.5, "prognose": 0.3}
    ampel, label = trend_ampel(trends)
    assert ampel == "gelb"
    assert "stagnierend" in label


def test_trend_ampel_dom_colors_override_heuristic() -> None:
    # Heuristik würde grün sagen, DOM sagt explizit rot
    trends = {"jahre_3": 5.0, "jahr_1": 3.0, "prognose": 2.0}
    dom = {"jahre_3": "rot", "jahr_1": "rot", "prognose": "gelb"}
    ampel, _ = trend_ampel(trends, dom_colors=dom)
    assert ampel == "rot"


def test_build_trend_label_full_with_emoji() -> None:
    marktwert = {"min": 168_000, "max": 178_000, "mittel": 173_000}
    trends = {"jahre_3": 6.7, "jahr_1": 3.0, "prognose": 1.4}
    out = build_trend_label(
        marktwert=marktwert, trends=trends, ampel="gruen", ampel_label="steigend"
    )
    assert "168.000" in out
    assert "178.000" in out
    assert "173.000" in out
    assert "+6.7% 3J" in out
    assert "+3.0% 1J" in out
    assert "+1.4% Prognose" in out
    assert "🟢" in out


def test_build_trend_label_without_prognose() -> None:
    marktwert = {"min": None, "max": None, "mittel": 200_000}
    trends = {"jahre_3": 4.0, "jahr_1": 1.5, "prognose": None}
    out = build_trend_label(
        marktwert=marktwert, trends=trends, ampel="gelb", ampel_label="stagnierend"
    )
    assert "200.000" in out
    assert "🟡" in out
    assert "+4.0% 3J" in out
    assert "+1.5% 1J" in out
    assert "Prognose" not in out


def test_build_trend_label_does_not_contain_portal_prefix() -> None:
    # core/parsers darf KEIN Portal kennen
    marktwert = {"min": 100_000, "max": 110_000, "mittel": 105_000}
    trends = {"jahre_3": 1.0, "jahr_1": 0.5, "prognose": 0.3}
    out = build_trend_label(
        marktwert=marktwert, trends=trends, ampel="gelb", ampel_label="stagnierend"
    )
    assert "CHECK24" not in out
    assert "PriceHugger" not in out
