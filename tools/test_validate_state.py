"""Tests für validate_state.py — Schema-Validator.

Lauf: pytest tools/test_validate_state.py -v
Voraussetzung: pip install jsonschema pytest
"""
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "tools" / "validate_state.py"


def _run(state_obj, tmp_path) -> tuple[int, str]:
    """Validator auf state-Dict laufen lassen, (returncode, stderr) zurück."""
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state_obj), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(VALIDATOR), str(state_file)],
        capture_output=True, text=True
    )
    return proc.returncode, proc.stderr


def _minimal_valid_state() -> dict:
    return {
        "schema_version": "1.0",
        "objekt": {
            "slug": "teststr-1-essen",
            "adresse": "Teststr. 1, 45000 Essen",
            "stadt": "Essen",
            "bundesland": "NRW",
            "erstellt_am": "2026-05-12",
            "letzter_modul_lauf": "modul_0",
        },
    }


def test_minimal_state_is_valid(tmp_path):
    rc, _ = _run(_minimal_valid_state(), tmp_path)
    assert rc == 0


def test_missing_schema_version_fails(tmp_path):
    state = _minimal_valid_state()
    del state["schema_version"]
    rc, err = _run(state, tmp_path)
    assert rc != 0
    assert "schema_version" in err


def test_invalid_slug_fails(tmp_path):
    state = _minimal_valid_state()
    state["objekt"]["slug"] = "Teststr*1"  # Stern = Filesystem-verboten
    rc, err = _run(state, tmp_path)
    assert rc != 0
    assert "slug" in err


def test_neues_slug_format_valid(tmp_path):
    state = _minimal_valid_state()
    state["objekt"]["slug"] = "Vestische Straße 250, 46145 Oberhausen-Sterkrade"
    rc, _ = _run(state, tmp_path)
    assert rc == 0


def test_unbekannt_fallback_valid(tmp_path):
    state = _minimal_valid_state()
    state["objekt"]["slug"] = "unbekannt - a1b2c3d4"
    rc, _ = _run(state, tmp_path)
    assert rc == 0


def test_slug_mit_filesystem_verbotenem_zeichen_fails(tmp_path):
    state = _minimal_valid_state()
    state["objekt"]["slug"] = "Teststraße 1 <invalid>"  # < ist verboten
    rc, err = _run(state, tmp_path)
    assert rc != 0
    assert "slug" in err


def test_modul_2_rnd_frozen_must_be_true(tmp_path):
    state = _minimal_valid_state()
    state["modul_2"] = {
        "status": "gruen",
        "tiefenstufe": 2,
        "konfidenz": "mittel",
        "baujahr": 1968,
        "rnd_jahre": 45,
        "rnd_frozen": False,  # Verstoß
        "rnd_basis": "ImmoWertV Anlage 2",
        "mod_score": 60,
        "afa_korridor_prozent": {"min": 2.0, "max": 3.5},
        "afa_empfehlung_prozent": 2.5,
        "begruendung": "Test",
    }
    rc, err = _run(state, tmp_path)
    assert rc != 0
    assert "rnd_frozen" in err


def _minimal_modul_1() -> dict:
    """Schema-konformer minimaler modul_1-Block (ohne brw_quelle)."""
    return {
        "status": "gruen",
        "tiefenstufe": 3,
        "tiefenstufe_max": 5,
        "konfidenz": "mittel",
        "brw_eur_pro_qm": 330,
        "gebaeude_anteil_prozent": 70,
        "we_liste": [
            {
                "we_nr": 1,
                "lage_im_haus": "EG",
                "wohnflaeche_qm": 90,
                "zimmer_anzahl": 3,
                "balkon": True,
                "keller": True,
            }
        ],
    }


def test_modul_1_without_brw_quelle_is_valid(tmp_path):
    """Backwards-Compat: alte state.json ohne brw_quelle bleibt valide."""
    state = _minimal_valid_state()
    state["modul_1"] = _minimal_modul_1()
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_modul_1_with_full_brw_quelle_boris_auto_is_valid(tmp_path):
    state = _minimal_valid_state()
    state["modul_1"] = _minimal_modul_1()
    state["modul_1"]["brw_quelle"] = {
        "quelle": "BORIS.NRW_auto",
        "nutzungsart": "Misch-/Mehrgeschossig",
        "bodenrichtwertnummer": "12005",
        "gemarkung": "Eving",
        "ortsteil": "Eving",
        "stichtag": "2026-01-01",
        "abgerufen_am": "2026-05-19",
        "bestaetigte_adresse": "Deutsche Straße 59, 44339 Dortmund - Eving",
        "geocoding_score": 2.91,
    }
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_modul_1_brw_quelle_invalid_enum_rejected(tmp_path):
    state = _minimal_valid_state()
    state["modul_1"] = _minimal_modul_1()
    state["modul_1"]["brw_quelle"] = {
        "quelle": "Foo",  # nicht im Enum
        "abgerufen_am": "2026-05-19",
    }
    rc, err = _run(state, tmp_path)
    assert rc != 0
    assert "quelle" in err.lower() or "enum" in err.lower() or "foo" in err.lower()


def test_modul_1_brw_quelle_minimal_user_geschaetzt_is_valid(tmp_path):
    """Manueller Fallback: nur quelle + abgerufen_am gesetzt, Rest null/weg."""
    state = _minimal_valid_state()
    state["modul_1"] = _minimal_modul_1()
    state["modul_1"]["brw_quelle"] = {
        "quelle": "User_geschaetzt",
        "abgerufen_am": "2026-05-19",
    }
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_modul_3_subvention_in_massnahme_rejected(tmp_path):
    """Asset-Trennung: 'subvention' in massnahmen_liste-Eintrag muss als rot zurückgewiesen werden."""
    state = _minimal_valid_state()
    state["modul_3"] = {
        "status": "gruen",
        "tiefenstufe": 2,
        "konfidenz": "mittel",
        "ist_kernsanierung": False,
        "massnahmen_liste": [
            {"kategorie": "Sonstiges", "ist_zustand": "leer", "geplant": "Mietsubvention 2 Jahre",
             "kosten_netto_eur": 10000}
        ],
        "rnd_gutachten_netto_eur": 6000,
        "weg_teilung_netto_eur": 3000,
        "enev_klasse": "E",
        "summen": {
            "modernisierung_netto_eur": 100000,
            "modernisierung_brutto_eur": 119000,
            "nebenkosten_netto_eur": 9000,
            "nebenkosten_brutto_eur": 10710,
        },
    }
    rc, err = _run(state, tmp_path)
    assert rc != 0
    assert "asset-trennung" in err.lower() or "subvention" in err.lower()


def _minimal_modul_4() -> dict:
    """Schema-konformer minimaler modul_4-Block (ohne wohnlage-Sub-Objekt)."""
    return {
        "status": "gruen",
        "tiefenstufe": 4,
        "tiefenstufe_max": 6,
        "konfidenz": "mittel",
        "we_mieten": [
            {
                "we_nr": 1,
                "ist_miete_eur_pro_qm": 7.0,
                "sollmiete_eur_pro_qm": 6.5,
                "mietspiegel_obergrenze_eur_pro_qm": 7.8,
                "paragraph_558_heberecht_eur": 0.0,
                "mietsubvention_eur_pro_monat": 0.0,
            }
        ],
        "mietsubventionen_summe_eur_pro_monat": 0.0,
        "begruendung_je_we": {"1": "Test"},
    }


def test_modul_4_without_wohnlage_is_valid(tmp_path):
    """Backwards-Compat: state.json ohne wohnlage-Sub-Objekt bleibt valide."""
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_modul_4_with_full_wohnlage_high_confidence_is_valid(tmp_path):
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["wohnlage"] = {
        "klasse": "VI",
        "lage_korrektur_prozent": -1.9,
        "konfidenz_score": 85,
        "quellen_trail": [
            {"typ": "webfetch", "quelle": "https://www.essen.de/mietspiegel",
             "ergebnis": "Beisenstr. 52 → Wohnlage VI"},
            {"typ": "websearch", "quelle": "google",
             "ergebnis": "Stadtteil Katernberg ehemalige Bergmannssiedlung"},
            {"typ": "plausi_bestandsmieten", "quelle": "ist-mieten-median",
             "ergebnis": "Median 6,9 €/m² passt zu VI"},
        ],
        "begruendung": "Wohnlage VI gewählt auf Basis essen.de-Straßenverzeichnis und Plausibilisierung mit Bestandsmieten-Median.",
        "user_bestaetigt": False,
    }
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_modul_4_wohnlage_invalid_konfidenz_score_rejected(tmp_path):
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["wohnlage"] = {
        "klasse": "VI",
        "lage_korrektur_prozent": -1.9,
        "konfidenz_score": 150,  # > max 100
        "quellen_trail": [{"typ": "webfetch", "ergebnis": "x"}],
        "begruendung": "Test-Begruendung mit ausreichender Laenge.",
    }
    rc, err = _run(state, tmp_path)
    assert rc != 0
    err_l = err.lower()
    assert "konfidenz_score" in err_l or "maximum" in err_l or "100" in err


def test_modul_4_wohnlage_invalid_typ_enum_rejected(tmp_path):
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["wohnlage"] = {
        "klasse": "VI",
        "lage_korrektur_prozent": -1.9,
        "konfidenz_score": 80,
        "quellen_trail": [{"typ": "facebook", "ergebnis": "x"}],  # nicht im Enum
        "begruendung": "Test-Begruendung mit ausreichender Laenge.",
    }
    rc, err = _run(state, tmp_path)
    assert rc != 0
    err_l = err.lower()
    assert "facebook" in err_l or "enum" in err_l or "typ" in err_l


def test_modul_4_wohnlage_empty_quellen_trail_rejected(tmp_path):
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["wohnlage"] = {
        "klasse": "VI",
        "lage_korrektur_prozent": -1.9,
        "konfidenz_score": 80,
        "quellen_trail": [],  # verletzt minItems:1
        "begruendung": "Test-Begruendung mit ausreichender Laenge.",
    }
    rc, err = _run(state, tmp_path)
    assert rc != 0
    err_l = err.lower()
    assert "quellen_trail" in err_l or "minitems" in err_l or "empty" in err_l


def _modul_1_crm_state() -> dict:
    state = _minimal_valid_state()
    state["schema_version"] = "2.0"
    state["objekt"]["letzter_modul_lauf"] = "modul_1"
    state["modul_1"] = {
        "status": "gelb",
        "ausgefuehrt_am": "2026-06-03T11:40:00+02:00",
        "angebotspreis_eur": 600000,
        "gap_eur": -311296,
        "gap_prozent": -34.18,
        "scoring_gesamt": 5.7,
        "scoring_ampel": "gelb",
        "deal_id": "2d6761ba-bcaf-4c0d-8f30-e24d7120fe14",
        "kurz_fazit": "Verhandeln - KP 34 % unter Konsens.",
    }
    return state


def test_modul_1_crm_fields_deal_id_kurz_fazit_valid(tmp_path):
    """CRM-Pipeline (Modul 0 -> 1, Schritt Q) schreibt deal_id + kurz_fazit (Live-Test Cramerstr. 2026-10-23)."""
    rc, err = _run(_modul_1_crm_state(), tmp_path)
    assert rc == 0, err


def test_modul_1_kurz_fazit_must_be_string(tmp_path):
    state = _modul_1_crm_state()
    state["modul_1"]["kurz_fazit"] = 5
    rc, _ = _run(state, tmp_path)
    assert rc != 0


def test_modul_0_with_gap_ampel_is_valid(tmp_path):
    """gap_ampel ist neues optionales Feld (2026-05-22)."""
    state = _minimal_valid_state()
    state["modul_0"] = {
        "status": "gruen",
        "tiefenstufe": 1,
        "konfidenz": "hoch",
        "ausgefuehrt_am": "2026-05-22T10:00:00",
        "angebotspreis_eur": 500000,
        "etw_konsens_eur": 480000,
        "gap_prozent": 4.17,
        "ueber_schwelle": False,
        "gap_ampel": "gelb",
    }
    rc, err = _run(state, tmp_path)
    assert rc == 0, f"gap_ampel sollte erlaubt sein, stderr: {err}"


def test_modul_0_gap_ampel_invalid_value_fails(tmp_path):
    """gap_ampel muss aus dem status_enum kommen."""
    state = _minimal_valid_state()
    state["modul_0"] = {
        "status": "gruen",
        "tiefenstufe": 1,
        "konfidenz": "hoch",
        "ausgefuehrt_am": "2026-05-22T10:00:00",
        "angebotspreis_eur": 500000,
        "etw_konsens_eur": 480000,
        "gap_prozent": 4.17,
        "ueber_schwelle": False,
        "gap_ampel": "blau",
    }
    rc, _ = _run(state, tmp_path)
    assert rc != 0


def test_modul_0_with_marktpreis_ampel_is_valid(tmp_path):
    state = _minimal_valid_state()
    state["modul_0"] = {
        "status": "gruen",
        "tiefenstufe": 1,
        "konfidenz": "hoch",
        "ausgefuehrt_am": "2026-05-22T10:00:00",
        "angebotspreis_eur": 500000,
        "etw_konsens_eur": 480000,
        "gap_prozent": 4.17,
        "ueber_schwelle": False,
        "marktpreis_ampel": "gruen",
    }
    rc, err = _run(state, tmp_path)
    assert rc == 0, f"marktpreis_ampel sollte erlaubt sein, stderr: {err}"


def test_modul_0_with_ist_miete_aus_mietspiegel_is_valid(tmp_path):
    state = _minimal_valid_state()
    state["modul_0"] = {
        "status": "gruen",
        "tiefenstufe": 1,
        "konfidenz": "hoch",
        "ausgefuehrt_am": "2026-05-22T10:00:00",
        "angebotspreis_eur": 500000,
        "etw_konsens_eur": 480000,
        "gap_prozent": 4.17,
        "ueber_schwelle": False,
        "ist_miete_aus_mietspiegel": True,
    }
    rc, err = _run(state, tmp_path)
    assert rc == 0, f"ist_miete_aus_mietspiegel sollte erlaubt sein, stderr: {err}"


def _minimal_modul_0() -> dict:
    """Schema-konformer minimaler modul_0-Block."""
    return {
        "status": "gruen",
        "tiefenstufe": 1,
        "konfidenz": "hoch",
        "ausgefuehrt_am": "2026-05-25T10:00:00",
        "angebotspreis_eur": 500000,
        "etw_konsens_eur": 480000,
        "gap_prozent": 4.17,
        "ueber_schwelle": False,
    }


def test_modul0_ohne_gmb_fallback_quelle_ok(tmp_path):
    """Bestehende state.json ohne neue Sub-Blocks muss valide bleiben (additives Schema)."""
    state = _minimal_valid_state()  # vorhandener Helper
    state["modul_0"] = _minimal_modul_0()
    state["modul_0"].pop("gmb_fallback_quelle", None)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(state_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_modul0_gmb_fallback_quelle_valid(tmp_path):
    state = _minimal_valid_state()
    state["modul_0"] = _minimal_modul_0()
    state["modul_0"]["gmb_fallback_quelle"] = {
        "konfidenz_score": 85,
        "quellen_trail": [
            {"typ": "notion", "quelle": "page-id-xyz", "ergebnis": "Sub-Page gefunden"},
            {"typ": "stadt-webseite", "quelle": "https://bochum.de/gutachterausschuss", "ergebnis": "PDF-Link extrahiert"}
        ],
        "notion_page_id": "3370ae59-38e4-81ab-9637-c7f00fc4f4dc",
        "begruendung": "Sub-Page für Bochum GMB 2025 in Notion vorhanden; Stadtteil-Match Eppendorf.",
        "user_bestaetigt": False
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(state_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_modul0_gmb_fallback_invalid_konfidenz(tmp_path):
    state = _minimal_valid_state()
    state["modul_0"] = _minimal_modul_0()
    state["modul_0"]["gmb_fallback_quelle"] = {
        "konfidenz_score": 150,  # >100 ungültig
        "quellen_trail": [{"typ": "notion", "quelle": "x", "ergebnis": "y"}],
        "begruendung": "20-Zeichen-Mindestlänge erfüllt."
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(state_path)],
                            capture_output=True, text=True)
    assert result.returncode != 0


def test_modul4_mietspiegel_fallback_quelle_valid(tmp_path):
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["mietspiegel_fallback_quelle"] = {
        "konfidenz_score": 75,
        "quellen_trail": [{"typ": "stadt-webseite", "quelle": "https://hagen.de/mietspiegel.pdf", "ergebnis": "Basis-EUR/qm extrahiert"}],
        "notion_db_row_id": "row-uuid-here",
        "begruendung": "Hagen-Mietspiegel 2024 von hagen.de gezogen, Basis 5.80 EUR/qm Bj 1950-1977.",
        "user_bestaetigt": False
    }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(state_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_modul4_mietsubventionen_total_eur_valid(tmp_path):
    """Modul 5 schreibt das Total ueber die Reach-Time; das Schema muss es zulassen.

    Fehlte es, entfernte der Validator das Feld und Modul 6 fiel auf
    `summe_eur_pro_monat x 60` zurueck - in drei echten Objektlaeufen mit
    abweichenden Betraegen in VERKAUFSMATRIX!Y27.
    """
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["mietsubventionen_summe_eur_pro_monat"] = 613.0
    state["modul_4"]["mietsubventionen_total_eur"] = 42200.21
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_modul4_mietsubventionen_total_eur_negativ_abgelehnt(tmp_path):
    """Das Total ist ein Betrag; das Minuszeichen setzt erst Modul 6 in Y27."""
    state = _minimal_valid_state()
    state["modul_4"] = _minimal_modul_4()
    state["modul_4"]["mietsubventionen_total_eur"] = -42200.21
    rc, err = _run(state, tmp_path)
    assert rc != 0


def _minimal_valid_state_v2() -> dict:
    """Minimal-State in der aktuellen Fassung 2.0 (ab Modul-Umnummerierung 2026-05-26).

    Die uebrige Suite prueft ausschliesslich Fassung 1.0, obwohl alle neuen
    Objektlaeufe 2.0 schreiben. In 2.0 liegen die Mieten in modul_5.
    """
    state = _minimal_valid_state()
    state["schema_version"] = "2.0"
    state["objekt"]["letzter_modul_lauf"] = "modul_1"  # modul_0 gibt es in 2.0 nicht mehr
    return state


def test_v2_mietsubventionen_total_eur_valid(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_5"] = _minimal_modul_4()
    state["modul_5"]["mietsubventionen_summe_eur_pro_monat"] = 613.0
    state["modul_5"]["mietsubventionen_total_eur"] = 42200.21
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_v2_mietsubventionen_total_eur_negativ_abgelehnt(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_5"] = _minimal_modul_4()
    state["modul_5"]["mietsubventionen_total_eur"] = -1.0
    rc, err = _run(state, tmp_path)
    assert rc != 0


# ---- Felder der Verkaufs-Kalkulation (Fassung 2.0, seit 2026-09-10) ----

def _v2_state_mit_miete(**we_extra) -> dict:
    state = _minimal_valid_state_v2()
    state["modul_5"] = _minimal_modul_4()
    state["modul_5"]["we_mieten"][0].update(we_extra)
    return state


def test_v2_neue_mietfelder_valid(tmp_path):
    state = _v2_state_mit_miete(
        ist_miete_eur_pro_monat=450.0, leerstand=False, mieter_seit="2025-07-01",
        letzte_mieterhoehung="2013-01-01", reach_time_monate=0, garagen_anzahl=1,
        stellplaetze_anzahl=0, garage_miete_eur_pro_monat=55.0, stellplatz_miete_eur_pro_monat=0.0,
        hausgeld_nicht_umlagefaehig_eur_pro_monat=107.33, hausgeld_ruecklage_eur_pro_monat=72.33,
    )
    state["modul_5"]["kappungsgrenze"] = 0.2
    state["modul_5"]["paragraph_559_umlage_prozent"] = 0.0
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_v2_ruecklage_groesser_hausgeld_abgelehnt(tmp_path):
    state = _v2_state_mit_miete(hausgeld_nicht_umlagefaehig_eur_pro_monat=50.0, hausgeld_ruecklage_eur_pro_monat=60.0)
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "hausgeld_ruecklage" in err


def test_v2_hausgeld_ohne_ruecklage_abgelehnt(tmp_path):
    state = _v2_state_mit_miete(hausgeld_nicht_umlagefaehig_eur_pro_monat=50.0)
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "Paar-Pflicht" in err


def test_v2_quote_und_hausgeld_gleichzeitig_abgelehnt(tmp_path):
    state = _v2_state_mit_miete(hausgeld_nicht_umlagefaehig_eur_pro_monat=50.0, hausgeld_ruecklage_eur_pro_monat=10.0,
                                bewirtschaftungsquote_schaetzung=0.22)
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "nur eine Quelle" in err


def test_v2_ist_miete_null_mit_leerstand_false_abgelehnt(tmp_path):
    state = _v2_state_mit_miete(ist_miete_eur_pro_qm=0.0, leerstand=False)
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "leerstand" in err
    state = _v2_state_mit_miete(ist_miete_eur_pro_qm=0.0, leerstand=True)
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_v2_ist_miete_null_ohne_leerstand_feld_bleibt_valide(tmp_path):
    """Backwards-Compat: Laeufe vor 2026-09-10 haben kein leerstand-Feld (z.B. Frintroper Str. 17)."""
    state = _v2_state_mit_miete(ist_miete_eur_pro_qm=0.0)
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_v2_reach_time_passt_nicht_zur_subvention(tmp_path):
    state = _v2_state_mit_miete(mietsubvention_eur_pro_monat=65.87, reach_time_monate=0)
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "reach_time" in err


def test_v2_datum_muss_iso_sein(tmp_path):
    state = _v2_state_mit_miete(letzte_mieterhoehung="01.01.2013")
    rc, _ = _run(state, tmp_path)
    assert rc != 0


def _v2_modul_2() -> dict:
    return {
        "status": "gruen", "tiefenstufe": 3, "tiefenstufe_max": 5, "konfidenz": "hoch",
        "brw_eur_pro_qm": 235.0, "gebaeude_anteil_prozent": 81.42,
        "we_liste": [
            {"we_nr": 1, "lage_im_haus": "EG links", "wohnflaeche_qm": 53.0, "zimmer_anzahl": 2, "balkon": True, "keller": True, "mea_zaehler": 5300},
            {"we_nr": 2, "lage_im_haus": "EG rechts", "wohnflaeche_qm": 73.0, "zimmer_anzahl": 3, "balkon": True, "keller": True, "mea_zaehler": 7300},
        ],
    }


def test_v2_grundstueck_und_mea_valid(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_2"] = _v2_modul_2()
    state["modul_2"]["grundstuecksflaeche_qm"] = 1341.0
    state["modul_2"]["grundstuecksflaeche_quelle"] = {"quelle": "Grundbuch", "dokument": "Blatt 922", "flurstueck": "Flur 21, 288", "konfidenz": "hoch", "abgerufen_am": "2025-05-26"}
    state["modul_2"]["mea_nenner"] = 103000
    state["modul_2"]["mea_quelle"] = "Wohnflaechenanteil_geschaetzt"
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_v2_mea_zaehler_ueber_nenner_abgelehnt(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_2"] = _v2_modul_2()
    state["modul_2"]["mea_nenner"] = 10000
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "mea_nenner" in err


def test_v2_grundstuecksquelle_unbekannt_abgelehnt(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_2"] = _v2_modul_2()
    state["modul_2"]["grundstuecksflaeche_quelle"] = {"quelle": "Hoerensagen"}
    rc, _ = _run(state, tmp_path)
    assert rc != 0


def test_v2_leerstand_we_anzahl_in_modul_4(tmp_path):
    """Modul-4-Skill verlangt das Feld seit langem; das Schema kannte es nicht."""
    import pytest
    real = REPO_ROOT / "runs" / "Rautenstrauchstraße 1, 59075 Hamm" / "state.json"
    if not real.is_file():
        pytest.skip("Referenz-State nicht vorhanden")
    state = json.loads(real.read_text(encoding="utf-8"))
    state["modul_4"]["leerstand_we_anzahl"] = 0
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def _minimal_modul_2() -> dict:
    """Schema-konformer minimaler modul_2-Block (Fassung 2.0)."""
    return {
        "status": "gruen",
        "tiefenstufe": 2,
        "tiefenstufe_max": 5,
        "konfidenz": "mittel",
        "brw_eur_pro_qm": 235.0,
        "gebaeude_anteil_prozent": 82.2,
        "we_liste": [
            {"we_nr": 1, "lage_im_haus": "EG", "wohnflaeche_qm": 53.0, "zimmer_anzahl": 2, "balkon": False, "keller": True},
            {"we_nr": 2, "lage_im_haus": "OG_links", "wohnflaeche_qm": 73.0, "zimmer_anzahl": 3, "balkon": True, "keller": True},
        ],
    }


def _v2_state_mit_garagen(gesamt: int, preis, anzahl_je_we: tuple[int, ...]) -> dict:
    """Modul 2 haelt Bestand und Preis je Einheit, Modul 5 die Zuordnung je WE."""
    state = _minimal_valid_state_v2()
    state["modul_2"] = _minimal_modul_2()
    state["modul_2"]["garagen_gesamt"] = gesamt
    state["modul_2"]["stellplaetze_gesamt"] = 0
    if preis is not None:
        state["modul_2"]["garage_preis_eur"] = preis
        state["modul_2"]["garagen_preis_quelle"] = "geschaetzt"
    state["modul_5"] = _minimal_modul_4()
    state["modul_5"]["we_mieten"] = [
        dict(state["modul_5"]["we_mieten"][0], we_nr=i + 1, garagen_anzahl=n) for i, n in enumerate(anzahl_je_we)
    ]
    return state


def test_v2_garagen_bestand_und_preis_valid(tmp_path):
    rc, err = _run(_v2_state_mit_garagen(6, 10000.0, (1, 1)), tmp_path)
    assert rc == 0, err


def test_v2_garagen_je_we_ueber_bestand_abgelehnt(tmp_path):
    rc, err = _run(_v2_state_mit_garagen(1, 10000.0, (1, 1)), tmp_path)
    assert rc != 0 and "garagen_gesamt" in err


def test_v2_garagenpreis_ohne_bestand_abgelehnt(tmp_path):
    rc, err = _run(_v2_state_mit_garagen(0, 10000.0, (0, 0)), tmp_path)
    assert rc != 0 and "garagen_gesamt = 0" in err


def test_v2_garagenpreis_negativ_abgelehnt(tmp_path):
    rc, err = _run(_v2_state_mit_garagen(6, -1.0, (1, 0)), tmp_path)
    assert rc != 0


def _v2_modul_3(rnd_jahre: int) -> dict:
    return {
        "status": "gruen",
        "tiefenstufe": 2,
        "konfidenz": "mittel",
        "baujahr": 1905,
        "rnd_jahre": rnd_jahre,
        "rnd_frozen": True,
        "rnd_basis": "Basis-Formel (R05 oder Punkte < 2)",
        "mod_score": 0,
        "afa_korridor_prozent": {"min": 7.58, "max": 8.33},
        "afa_empfehlung_prozent": 7.95,
        "begruendung": "Test Mindest-RND",
    }


def test_v2_modul_3_mindest_rnd_12_valid(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_3"] = _v2_modul_3(12)
    rc, err = _run(state, tmp_path)
    assert rc == 0, err


def test_v2_modul_3_rnd_unter_12_abgelehnt(tmp_path):
    state = _minimal_valid_state_v2()
    state["modul_3"] = _v2_modul_3(11)
    rc, err = _run(state, tmp_path)
    assert rc != 0 and "rnd_jahre" in err
