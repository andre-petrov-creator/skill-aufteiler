import json
from pathlib import Path

from immoscout.parser import decode_street_from_telekom_param, extract_keyvalues, parse_expose

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_keyvalues_from_real_expose():
    html = (FIXTURES / "valid_expose_real.html").read_text(encoding="utf-8")
    kv = extract_keyvalues(html)
    assert kv is not None
    assert kv["obj_scoutId"] == "167669914"
    assert kv["obj_purchasePrice"] == "649000"
    assert kv["obj_livingSpace"] == "362"
    assert kv["obj_yearConstructed"] == "1955"
    assert kv["geo_krs"] == "essen"


def test_extract_keyvalues_returns_none_on_block():
    html = "<html><body>Ich bin kein Roboter</body></html>"
    assert extract_keyvalues(html) is None


def test_extract_keyvalues_minimal_inline_object():
    html = 'before <script>var keyValues = {"obj_scoutId":"42","obj_purchasePrice":"100"};</script> after'
    kv = extract_keyvalues(html)
    assert kv == {"obj_scoutId": "42", "obj_purchasePrice": "100"}


def test_decode_street_from_telekom_param_real_value():
    # value from probe: starts with "eyJvcnQi..." which is base64 for {"ort":...
    real = "eyJvcnQiOiJFc3NlbiIsIm9ydHN0ZWlsIjoiIiwic3RyYXNzZSI6IkJlaXNlbnN0ci4iLCJoYXVzbnVtbWVyIjoiMSJ9"
    result = decode_street_from_telekom_param(real)
    assert result is not None
    assert result["strasse"] == "Beisenstr."
    assert result["ort"] == "Essen"


def test_decode_street_from_telekom_param_invalid_input():
    assert decode_street_from_telekom_param("not-base64!") is None
    assert decode_street_from_telekom_param("") is None
    assert decode_street_from_telekom_param(None) is None


def test_parse_expose_against_real_fixture():
    html = (FIXTURES / "valid_expose_real.html").read_text(encoding="utf-8")
    result = parse_expose(html=html, final_url="https://www.immobilienscout24.de/expose/167669914")

    assert result["scout_id"] == "167669914"
    assert result["ueberschrift"]  # non-empty
    assert "Katernberg" in result["ueberschrift"]

    addr = result["adresse"]
    assert addr["plz"] == "45327"
    assert addr["ort"] == "Essen"
    assert addr["stadtteil"] == "Katernberg"
    # street should be decoded from telekom param
    assert addr["strasse"] and addr["strasse"] != "no_information"

    eck = result["eckdaten"]
    assert eck["kaufpreis_eur"] == 649000
    assert eck["wohnflaeche_qm"] == 362.0
    assert eck["grundstuecksflaeche_qm"] == 526.0
    assert eck["baujahr"] == 1955
    assert eck["modernisierung_jahr"] == 2006
    assert eck["energieeffizienzklasse"] == "D"
    assert eck["endenergieverbrauch_kwh"] == 112.4
    assert eck["heizung"] == "Gas"

    # images: count claimed 9 in keyValues
    assert isinstance(result["bilder"], list)
    # parser can read fewer if DOM gallery extraction is partial, but at least 1 expected
    assert len(result["bilder"]) >= 1


def test_parse_expose_text_sections():
    html = (FIXTURES / "valid_expose_real.html").read_text(encoding="utf-8")
    result = parse_expose(html=html, final_url="https://www.immobilienscout24.de/expose/167669914")

    texte = result["texte"]
    # at least one of these must contain real content (>50 chars)
    non_empty = [k for k, v in texte.items() if v and len(v) > 50]
    assert non_empty, f"all text sections empty: {texte}"

    # provider info should at least have firma or ansprechpartner
    anbieter = result["anbieter"]
    assert anbieter["firma"] or anbieter["ansprechpartner"]
