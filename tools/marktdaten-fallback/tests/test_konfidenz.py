"""Tests fuer konfidenz.py (Konfidenz-Aggregation + Gate)."""

from konfidenz import aggregate_konfidenz, gate_passed


def test_empty_trail_returns_zero():
    assert aggregate_konfidenz([]) == 0


def test_notion_treffer_alone_below_gate():
    trail = [{"quelle": "notion_mietspiegel", "status": "hit", "bonus": 50}]
    score = aggregate_konfidenz(trail)
    assert score == 50
    assert not gate_passed(score)


def test_combined_notion_plus_stadt_webseite_passes_gate():
    trail = [
        {"quelle": "notion_mietspiegel", "status": "hit", "bonus": 50},
        {"quelle": "stadt_webseite", "status": "hit", "bonus": 30},
    ]
    score = aggregate_konfidenz(trail)
    assert score == 80
    assert gate_passed(score)


def test_fail_entries_zero_bonus():
    trail = [
        {"quelle": "notion_mietspiegel", "status": "miss", "bonus": 0},
        {"quelle": "gmb_search", "status": "fail", "bonus": 0},
    ]
    score = aggregate_konfidenz(trail)
    assert score == 0
    assert not gate_passed(score)


def test_cap_at_100():
    trail = [
        {"quelle": "notion_mietspiegel", "status": "hit", "bonus": 80},
        {"quelle": "stadt_webseite", "status": "hit", "bonus": 50},
    ]
    score = aggregate_konfidenz(trail)
    assert score == 100


def test_gate_passed_threshold_exact():
    assert gate_passed(70) is True
    assert gate_passed(69) is False
