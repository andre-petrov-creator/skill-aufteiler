"""Unit-Tests für Homeday-spezifische Parser (Body-Text → strukturierte Werte)."""
from __future__ import annotations

import pytest

from portals.homeday.parsers import (
    WOHNLAGE_FARBE_MAP,
    parse_eur_per_qm,
    parse_trend_12m,
    parse_wohnblock_wohnlage,
    trend_ampel_homeday,
    wohnlage_farbe,
)


# Beispiel-Text, wie er aus read_frame/page_body_deep kommt (vereinfacht).
BODY_PROSPER = (
    "Prosperstraße 59\n"
    "45357 Dellwig, Essen\n"
    "Wohnungen\n"
    "Aktueller Kaufpreis\n"
    "i\n"
    "Ø 1.700 €/m²\n"
    "Sie möchten Ihre Immobilie verkaufen?\n"
    "Kostenlose Bewertung buchen\n"
    "Mehr über Homeday erfahren\n"
    "PREISTREND ÜBER 12 MONATE\n"
    "Stadt\n"
    "+6 %\n"
    "Wohnblock\n"
    "—\n"
    "Preisverlauf über 3 Jahre\n"
    "Wohnlage\n"
    "Einfach\n"
    "i\n"
)

BODY_GROSSSTADT = (
    "Aktueller Kaufpreis\n"
    "Ø 5.250 €/m²\n"
    "PREISTREND ÜBER 12 MONATE\n"
    "Stadt\n"
    "+2,5 %\n"
    "Wohnblock\n"
    "-1,8 %\n"
    "Wohnlage\n"
    "Sehr gut\n"
)


def test_parse_eur_per_qm_from_avg_block() -> None:
    assert parse_eur_per_qm(BODY_PROSPER) == 1700


def test_parse_eur_per_qm_with_comma_decimals() -> None:
    assert parse_eur_per_qm("Ø 1.234 €/m²") == 1234


def test_parse_eur_per_qm_returns_none_when_missing() -> None:
    assert parse_eur_per_qm("Keine Werte hier") is None


def test_parse_trend_12m_stadt_positive() -> None:
    out = parse_trend_12m(BODY_PROSPER)
    assert out["stadt"] == 6.0
    assert out["wohnblock"] is None  # "—" → None


def test_parse_trend_12m_both_values_with_decimal_and_sign() -> None:
    out = parse_trend_12m(BODY_GROSSSTADT)
    assert out["stadt"] == 2.5
    assert out["wohnblock"] == -1.8


def test_parse_wohnblock_wohnlage_einfach() -> None:
    assert parse_wohnblock_wohnlage(BODY_PROSPER) == "einfach"


def test_parse_wohnblock_wohnlage_sehr_gut() -> None:
    assert parse_wohnblock_wohnlage(BODY_GROSSSTADT) == "sehr gut"


def test_parse_wohnblock_wohnlage_returns_none_if_missing() -> None:
    assert parse_wohnblock_wohnlage("Kein Wohnlage-Block") is None


def test_trend_ampel_homeday_positive_above_one_percent_is_gruen() -> None:
    ampel, label = trend_ampel_homeday(6.0)
    assert ampel == "gruen"
    assert "steigend" in label


def test_trend_ampel_homeday_within_plus_minus_one_is_gelb() -> None:
    ampel, _ = trend_ampel_homeday(0.5)
    assert ampel == "gelb"
    ampel2, _ = trend_ampel_homeday(-0.8)
    assert ampel2 == "gelb"


def test_trend_ampel_homeday_negative_below_minus_one_is_rot() -> None:
    ampel, label = trend_ampel_homeday(-3.0)
    assert ampel == "rot"
    assert "fallend" in label


def test_trend_ampel_homeday_none_returns_grau() -> None:
    ampel, label = trend_ampel_homeday(None)
    assert ampel == "grau"
    assert "keine daten" in label.lower() or label == "—"


def test_wohnlage_farbe_einfach_is_yellow() -> None:
    assert wohnlage_farbe("einfach") == "#FFE873"  # gelb


def test_wohnlage_farbe_herausragend_is_purple() -> None:
    assert wohnlage_farbe("herausragend") == "#7B2D8E"  # lila


def test_wohnlage_farbe_unknown_returns_none() -> None:
    assert wohnlage_farbe("undefiniert") is None


def test_wohnlage_farbe_map_has_five_levels() -> None:
    assert set(WOHNLAGE_FARBE_MAP.keys()) == {
        "einfach", "mittel", "gut", "sehr gut", "herausragend"
    }
