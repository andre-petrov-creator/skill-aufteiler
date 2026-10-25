"""Konfidenz-Aggregation analog Modul-4 Wohnlage-Reasoning."""

from typing import List, Dict, Any

KONFIDENZ_GATE = 70


def aggregate_konfidenz(quellen_trail: List[Dict[str, Any]]) -> int:
    """Summe aller bonus-Eintraege im trail, gecapped auf 0..100.

    Jeder Trail-Eintrag muss ein 'bonus'-Feld haben (int).
    Fail-Eintraege bringen 0 Bonus.
    """
    total = sum(int(e.get("bonus", 0)) for e in quellen_trail)
    return max(0, min(100, total))


def gate_passed(score: int) -> bool:
    """True wenn der aggregierte Score den Gate-Wert erreicht (>= 70)."""
    return score >= KONFIDENZ_GATE
