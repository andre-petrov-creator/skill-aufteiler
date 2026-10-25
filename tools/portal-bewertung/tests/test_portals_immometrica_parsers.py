"""Tests fuer den Immometrica-Parser auf Body-Texten aus echten DOM-Dumps."""
from __future__ import annotations

import sys
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from portals.immometrica.parsers import (
    _parse_float_eu,
    _parse_int,
    parse_stat_block,
    parse_geo_state,
)


# --- Helpers ---------------------------------------------------------------


def test_parse_int_normal():
    assert _parse_int("32") == 32


def test_parse_int_thousand_separator():
    assert _parse_int("1.440") == 1440
    assert _parse_int("7.267") == 7267


def test_parse_int_empty():
    assert _parse_int("") is None
    assert _parse_int("   ") is None


def test_parse_float_eu_simple_decimal():
    assert _parse_float_eu("6,1") == 6.1
    assert _parse_float_eu("13,67") == 13.67
    assert _parse_float_eu("9,95") == 9.95


def test_parse_float_eu_thousand_separator():
    # "1.950 €" → 1950.0 (Tausender-Punkt, kein Dezimal)
    assert _parse_float_eu("1.950") == 1950.0
    assert _parse_float_eu("3.286") == 3286.0


def test_parse_float_eu_mixed():
    # "1.234,56" → 1234.56
    assert _parse_float_eu("1.234,56") == 1234.56


# --- Block parsing ---------------------------------------------------------


def test_parse_etw_kauf_with_mieten_zusatz():
    body = (
        "irgendein vorspann\n"
        "Übersicht: Wohnung kaufen\n"
        "Anzahl\nAngebote\n409\n"
        "Median Preis\npro m²\n1.950 €\n"
        "Median Onlinezeit\nin Tagen\n34\n"
        "Rendite\n6,1 %\n"
        "Zusatzinfo: Wohnung mieten\n"
        "Anzahl\nAngebote\n7267\n"
        "Median Preis\npro m²\n9,95 €\n"
        "Median Onlinezeit\nin Tagen\n14\n"
        "Angebote (Zimmer)\nKaufpreis (Zimmer)\n"
    )
    out = parse_stat_block(body)
    u = out["uebersicht"]
    z = out["zusatzinfo"]
    assert u is not None
    assert u["heading"] == "Wohnung kaufen"
    assert u["anzahl_angebote"] == 409
    assert u["median_preis_eur_per_qm"] == 1950.0
    assert u["median_onlinezeit_tage"] == 34
    assert u["rendite_pct"] == 6.1
    assert z is not None
    assert z["heading"] == "Wohnung mieten"
    assert z["anzahl_angebote"] == 7267
    assert z["median_preis_eur_per_qm"] == 9.95
    assert z["median_onlinezeit_tage"] == 14
    assert z["rendite_pct"] is None


def test_parse_mfh_kauf_with_mieten_zusatz():
    body = (
        "Übersicht: Haus kaufen\n"
        "Anzahl\nAngebote\n1440\n"
        "Median Preis\npro m²\n3.286 €\n"
        "Median Onlinezeit\nin Tagen\n41\n"
        "Rendite\n5,0 %\n"
        "Zusatzinfo: Haus mieten\n"
        "Anzahl\nAngebote\n108\n"
        "Median Preis\npro m²\n13,67 €\n"
        "Median Onlinezeit\nin Tagen\n15\n"
    )
    out = parse_stat_block(body)
    assert out["uebersicht"]["anzahl_angebote"] == 1440
    assert out["uebersicht"]["median_preis_eur_per_qm"] == 3286.0
    assert out["uebersicht"]["rendite_pct"] == 5.0
    assert out["zusatzinfo"]["anzahl_angebote"] == 108
    assert out["zusatzinfo"]["median_preis_eur_per_qm"] == 13.67


def test_parse_empty_body():
    out = parse_stat_block("")
    assert out["uebersicht"] is None
    assert out["zusatzinfo"] is None


def test_parse_only_uebersicht_no_zusatz():
    body = (
        "Übersicht: Wohnung kaufen\n"
        "Anzahl\nAngebote\n50\n"
        "Median Preis\npro m²\n2.000 €\n"
        "Median Onlinezeit\nin Tagen\n40\n"
        "Rendite\n5,5 %\n"
    )
    out = parse_stat_block(body)
    assert out["uebersicht"] is not None
    assert out["uebersicht"]["anzahl_angebote"] == 50
    assert out["zusatzinfo"] is None


def test_parse_geo_state_essen():
    body = (
        "Ort\nIm Baum auswählen\n"
        " Essen, Nordrhein-Westfalen\n"
        "Essen, Nordrhein-Westfalen\n"
        "Umkreis auswählen\n"
    )
    geo = parse_geo_state(body)
    assert geo == "Essen, Nordrhein-Westfalen"


def test_parse_geo_state_plz():
    body = (
        "Ort\nIm Baum auswählen\n"
        " 45357 Essen\n"
        "Umkreis auswählen\n"
    )
    geo = parse_geo_state(body)
    assert geo == "45357 Essen"


def test_parse_geo_state_none():
    geo = parse_geo_state("kein Ort hier")
    assert geo is None


def test_real_dom_dump_config_6():
    """Echter DOM-Dump vom Live-Lauf 2026-05-19T101105."""
    p = PROJ_ROOT / "runs" / "2026-05-19T101105_immometrica_auto_stats_6_essen_hauskauf_mfh_dom.json"
    if not p.exists():
        return  # skip wenn DOM-Dump nicht da
    import json
    d = json.load(open(p, encoding="utf-8"))
    body = d.get("body", "")
    out = parse_stat_block(body)
    assert out["uebersicht"] is not None
    assert out["uebersicht"]["heading"] == "Haus kaufen"
    assert out["uebersicht"]["anzahl_angebote"] == 1440
    assert out["uebersicht"]["median_preis_eur_per_qm"] == 3286.0
    assert out["uebersicht"]["median_onlinezeit_tage"] == 41
    assert out["uebersicht"]["rendite_pct"] == 5.0
    assert out["zusatzinfo"] is not None
    assert out["zusatzinfo"]["heading"] == "Haus mieten"
    assert out["zusatzinfo"]["anzahl_angebote"] == 108
    assert out["zusatzinfo"]["median_preis_eur_per_qm"] == 13.67


def test_real_dom_dump_config_1():
    """Echter DOM-Dump vom Live-Lauf — ETW-Statistik."""
    p = PROJ_ROOT / "runs" / "2026-05-19T101105_immometrica_auto_stats_1_plz_etw_kauf_dom.json"
    if not p.exists():
        return
    import json
    d = json.load(open(p, encoding="utf-8"))
    body = d.get("body", "")
    out = parse_stat_block(body)
    # Anzahl 409, Preis 1.950, Online 34, Rendite 6,1
    assert out["uebersicht"]["anzahl_angebote"] == 409
    assert out["uebersicht"]["median_preis_eur_per_qm"] == 1950.0
    assert out["uebersicht"]["rendite_pct"] == 6.1
    # Zusatzinfo Wohnung mieten: 7267, 9,95, 14
    assert out["zusatzinfo"]["anzahl_angebote"] == 7267
    assert out["zusatzinfo"]["median_preis_eur_per_qm"] == 9.95
