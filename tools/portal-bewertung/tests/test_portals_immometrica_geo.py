"""Tests fuer den Geo-Gate des Immometrica-Adapters.

Hintergrund (Ausfall 2026-09-10): Wenn der Ort-Filter nicht gesetzt ist, zeigt
das Widget den leeren Slot 'Neuer Ort' und Immometrica liefert **bundesweite**
Zahlen. Der Adapter meldete die als PLZ-Werte mit `status: ok`
(41284 Angebote / 3341 EUR/m2 statt 52 / 1878 fuer 45355 Essen).

`_geo_state_matches` ist die Gegenprobe, die das unmoeglich macht.
"""
import sys
from pathlib import Path

import pytest

PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from portals.immometrica.portal import _geo_state_matches  # noqa: E402


# ============================================================
# Treffer
# ============================================================

def test_plz_tag_matches_plz_query():
    assert _geo_state_matches("45355 Essen", "45355") is True


def test_stadt_tag_matches_stadt_query():
    assert _geo_state_matches("Essen, Nordrhein-Westfalen", "Essen") is True


def test_match_is_case_insensitive():
    assert _geo_state_matches("Essen, Nordrhein-Westfalen", "essen") is True


def test_surrounding_whitespace_is_tolerated():
    assert _geo_state_matches("  45355 Essen  ", "45355") is True


# ============================================================
# Der eigentliche Ausfall-Modus
# ============================================================

def test_empty_slot_never_matches():
    """'Neuer Ort' = kein Filter = bundesweite Zahlen."""
    assert _geo_state_matches("Neuer Ort", "45355") is False
    assert _geo_state_matches("Neuer Ort", "Essen") is False


@pytest.mark.parametrize("geo_state", [None, "", "   "])
def test_missing_geo_state_never_matches(geo_state):
    assert _geo_state_matches(geo_state, "45355") is False


def test_wrong_city_does_not_match():
    assert _geo_state_matches("Dortmund, Nordrhein-Westfalen", "Essen") is False


def test_wrong_plz_does_not_match():
    assert _geo_state_matches("45357 Essen", "45355") is False


def test_stale_plz_tag_does_not_confirm_city_config():
    """Nach dem Geo-Wechsel PLZ -> Stadt darf ein haengengebliebener
    PLZ-Tag die Stadt-Config nicht bestaetigen, obwohl er den Stadtnamen
    enthaelt."""
    assert _geo_state_matches("45355 Essen", "Essen") is False


def test_city_tag_still_matches_city_config():
    """Gegenprobe zum Test darueber: der echte Stadt-Tag muss durchgehen."""
    assert _geo_state_matches("Essen, Nordrhein-Westfalen", "Essen") is True
