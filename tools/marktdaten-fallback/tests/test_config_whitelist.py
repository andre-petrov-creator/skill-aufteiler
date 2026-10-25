from config import (
    is_whitelisted_url,
    get_stadt_mietspiegel_url,
    get_boris_index_url,
    WHITELIST_DOMAINS,
)


def test_official_domains_whitelisted():
    assert is_whitelisted_url("https://bochum.de/gutachterausschuss")
    assert is_whitelisted_url("https://www.essen.de/leben/wohnen/mietspiegel.de.html")
    assert is_whitelisted_url("https://boris.nrw.de/borisplus/")
    assert is_whitelisted_url("https://geoportal.nrw.de/")
    assert is_whitelisted_url("https://opengeodata.nrw.de/")
    assert is_whitelisted_url("https://www.gars.nrw/images/user/GA_Kreis_Recklinghausen/gmb/GMB_322_2024_pflichtig.pdf")
    assert is_whitelisted_url("https://gars.nrw/images/user/GA_Krefeld/pdf/GMB/GARS-KR-GMB-2025.pdf")


def test_third_party_rejected():
    assert not is_whitelisted_url("https://immowelt.de/x")
    assert not is_whitelisted_url("https://www.immobilienscout24.de/")
    assert not is_whitelisted_url("https://miet-check.de/y")


def test_gutachterausschuss_subdomain_whitelisted():
    assert is_whitelisted_url("https://www.gutachterausschuss-bochum.de/")


def test_stadt_mietspiegel_url_known_cities():
    assert get_stadt_mietspiegel_url("essen") == "https://www.essen.de/leben/wohnen/mietspiegel.de.html"
    assert get_stadt_mietspiegel_url("dortmund") == "https://www.dortmund.de/themen/bauen-und-wohnen/mietspiegel/"
    assert get_stadt_mietspiegel_url("bochum") == "https://www.bochum.de/Wohnen-und-Bauen/Mietspiegel"
    assert get_stadt_mietspiegel_url("oberhausen") == "https://www.oberhausen.de/de/index/rathaus/buergerservice/dienstleistungen/mietspiegel.php"
    assert get_stadt_mietspiegel_url("duesseldorf") == "https://www.duesseldorf.de/wohnungsamt/mietspiegel.html"


def test_stadt_mietspiegel_url_case_insensitive():
    assert get_stadt_mietspiegel_url("Essen") == get_stadt_mietspiegel_url("essen")
    assert get_stadt_mietspiegel_url("ESSEN") == get_stadt_mietspiegel_url("essen")


def test_stadt_mietspiegel_url_unknown_city_returns_none():
    assert get_stadt_mietspiegel_url("kleinkleckersdorf") is None


def test_boris_index_url_returns_nrw_root():
    url = get_boris_index_url()
    assert url.startswith("https://")
    assert "boris.nrw.de" in url
