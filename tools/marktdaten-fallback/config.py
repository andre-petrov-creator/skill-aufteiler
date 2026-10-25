"""Whitelist offizieller Domains + Stadt-Mietspiegel-URLs + BORIS-Index.

Hardes Constraint aus Spec: nur offizielle Quellen.
"""

from urllib.parse import urlparse
from typing import Optional


WHITELIST_DOMAINS = {
    # NRW-Geoportal + INSPIRE + offizielle GAA-Plattformen
    "boris.nrw.de",
    "gars.nrw",
    "geoportal.nrw.de",
    "opengeodata.nrw.de",
    "gdi-de.org",
    # Stadt-Domains Ruhrgebiet + Düsseldorf
    "essen.de", "dortmund.de", "bochum.de", "oberhausen.de", "duesseldorf.de",
    "hagen.de", "herne.de", "hamm.de", "iserlohn.de", "muelheim-ruhr.de",
    "gelsenkirchen.de", "bottrop.de", "recklinghausen.de", "wuppertal.de",
    "koeln.de", "bonn.de",
    # Kreise + Gemeinden im Aufteiler-Raum
    "kreis-unna.de", "kreis-recklinghausen.de", "ennepe-ruhr-kreis.de",
    # Generisches Pattern: gutachterausschuss-*.de
    # → wird per Subdomain-Match unten erkannt
    # Notion-internes (für quellen_trail-typ=notion)
    "notion.so",
}

GUTACHTERAUSSCHUSS_SUBDOMAIN_PREFIX = "gutachterausschuss-"


STADT_MIETSPIEGEL_URLS = {
    "essen": "https://www.essen.de/leben/wohnen/mietspiegel.de.html",
    "dortmund": "https://www.dortmund.de/themen/bauen-und-wohnen/mietspiegel/",
    "bochum": "https://www.bochum.de/Wohnen-und-Bauen/Mietspiegel",
    "oberhausen": "https://www.oberhausen.de/de/index/rathaus/buergerservice/dienstleistungen/mietspiegel.php",
    "duesseldorf": "https://www.duesseldorf.de/wohnungsamt/mietspiegel.html",
}


BORIS_NRW_INDEX_URL = "https://www.boris.nrw.de/borisplus/portal/"


def is_whitelisted_url(url: str) -> bool:
    """True wenn die URL-Hostname (oder Subdomain davon) auf der Whitelist ist."""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    # Direkter Match
    if host in WHITELIST_DOMAINS:
        return True
    # Subdomain-Match auf Whitelist-Domain (z.B. "alt.bochum.de" ist OK weil bochum.de drin)
    for domain in WHITELIST_DOMAINS:
        if host.endswith("." + domain):
            return True
    # Gutachterausschuss-Pattern: gutachterausschuss-<stadt>.de
    if host.startswith(GUTACHTERAUSSCHUSS_SUBDOMAIN_PREFIX) and host.endswith(".de"):
        return True
    return False


def get_stadt_mietspiegel_url(stadt: str) -> Optional[str]:
    """Vorab-URL für Stadt-Mietspiegel, case-insensitive. None falls Stadt unbekannt."""
    return STADT_MIETSPIEGEL_URLS.get(stadt.lower())


def get_boris_index_url() -> str:
    return BORIS_NRW_INDEX_URL
