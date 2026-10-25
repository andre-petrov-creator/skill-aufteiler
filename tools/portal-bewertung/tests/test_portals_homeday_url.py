"""Unit-Tests für Homeday-URL-Builder + Slug-Funktionen."""
from __future__ import annotations

from portals.homeday.selectors import (
    _slugify_stadt,
    _slugify_strasse,
    build_result_url,
)


def test_slugify_strasse_umlauts_and_ss() -> None:
    assert _slugify_strasse("Prosperstraße") == "prosperstrasse"
    assert _slugify_strasse("Müllerstraße") == "muellerstrasse"
    assert _slugify_strasse("Bahnhofstr.") == "bahnhofstr."


def test_slugify_stadt_with_spaces_and_umlauts() -> None:
    assert _slugify_stadt("Mülheim an der Ruhr") == "muelheim-an-der-ruhr"
    assert _slugify_stadt("Essen") == "essen"
    assert _slugify_stadt("Frankfurt am Main") == "frankfurt-am-main"


def test_build_result_url_with_hausnr() -> None:
    url = build_result_url(
        strasse="Prosperstraße", hausnr="59", plz="45357", ort="Essen"
    )
    assert url == (
        "https://www.homeday.de/de/preisatlas/essen/prosperstrasse+59,+45357"
        "?map_layer=standard&marketing_type=sell&property_type=apartment"
    )


def test_build_result_url_without_hausnr() -> None:
    """Wenn Hausnr fehlt, akzeptiert Homeday nur Straße + PLZ."""
    url = build_result_url(
        strasse="Prosperstraße", hausnr="", plz="45357", ort="Essen"
    )
    assert "prosperstrasse,+45357" in url


def test_build_result_url_rent_house_combo() -> None:
    url = build_result_url(
        strasse="Bahnhofstr.", hausnr="1", plz="10115", ort="Berlin",
        marketing_type="rent", property_type="house",
    )
    assert "berlin/bahnhofstr.+1,+10115" in url
    assert "marketing_type=rent" in url
    assert "property_type=house" in url


def test_build_result_url_invalid_marketing_type_still_passes() -> None:
    """build_result_url validiert nicht — Validation passiert anderswo."""
    url = build_result_url(
        strasse="X", hausnr="1", plz="00000", ort="Y", marketing_type="weird"
    )
    assert "marketing_type=weird" in url
