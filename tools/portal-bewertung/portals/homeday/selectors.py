"""DOM-Selektoren + URL-Bauer für homeday.de/de/preisatlas.

Stand: 2026-05-15 — live verifiziert via inspectors/dump_homeday_result.py.

Architektur-Eigenheit: Homeday bietet einen Deep-Link, der das Formular
überspringt. Der Adapter navigiert direkt zur Result-URL — das ist
robuster und schneller als Form-Befüllung.

URL-Schema:
  https://www.homeday.de/de/preisatlas/<stadt>/<strasse>+<hausnr>,+<plz>
    ?map_layer=standard
    &marketing_type=<sell|rent>
    &property_type=<apartment|house>

Cookie-Banner: Cookiebot (über consentcdn.cookiebot.com, im Hauptframe als
<a>-Tag), NICHT <button>. Daher mit ID-Selektor klicken.

Result-Seite: Single-Page-Anwendung, KEIN iframe. Werte werden aus dem
sichtbaren Body-Text per Regex extrahiert (siehe parsers.py).
"""
from __future__ import annotations

import re
from urllib.parse import quote

START_URL = "https://www.homeday.de/de/preisatlas"

COOKIE_ACCEPT_CANDIDATES = [
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    'a:has-text("Alle akzeptieren")',
    'button:has-text("Alle akzeptieren")',
]
COOKIE_WRAPPER = "#CybotCookiebotDialog"

# Adress-Eingabefeld auf der Startseite (für Fallback, falls Deep-Link nicht klappt)
ADDRESS_INPUT = 'input[placeholder*="straße" i]'

# Result-Frame-Marker: nicht im Frame, sondern im Page-Body — wir nutzen den
# Aktueller-Kaufpreis-Marker als Existenz-Check
RESULT_FRAME_MARKER = "Aktueller Kaufpreis"

# CSS-Selektoren der Werte auf der Result-Seite (zur Diagnose / Fallback)
SEL_EUR_PER_QM = ".price-block__price__average"  # "Ø 1.700 €/m²"
SEL_PRICE_TREND_BLOCK = ".price-trend__title"     # "PREISTREND ÜBER 12 MONATE"
SEL_PRICE_CHART_TITLE = ".price-chart__title"     # "Preisverlauf über 3 Jahre"
SEL_MAP_LEGEND_TITLE = ".map-legend__title"       # "Wohnlage"


def _slugify_strasse(strasse: str) -> str:
    """Konvertiert 'Prosperstraße' → 'prosperstrasse', URL-tauglich."""
    s = strasse.strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9\s\-\.]", "", s)
    s = re.sub(r"\s+", "", s)
    return s


def _slugify_stadt(ort: str) -> str:
    """Konvertiert 'Mülheim an der Ruhr' → 'muelheim-an-der-ruhr'."""
    s = ort.strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def build_result_url(
    *,
    strasse: str,
    hausnr: str,
    plz: str,
    ort: str,
    marketing_type: str = "sell",  # "sell" | "rent"
    property_type: str = "apartment",  # "apartment" | "house"
) -> str:
    """Baut die Deep-Link-URL für die Result-Seite.

    Beispiel:
      build_result_url(strasse="Prosperstraße", hausnr="59", plz="45357",
                       ort="Essen")
      → 'https://www.homeday.de/de/preisatlas/essen/prosperstrasse+59,+45357'
        '?map_layer=standard&marketing_type=sell&property_type=apartment'

    Hinweis: Wenn `hausnr` leer ist, wird nur `<strasse>,+<plz>` in der URL
    benutzt — Homeday akzeptiert das.
    """
    stadt_slug = _slugify_stadt(ort)
    strasse_slug = _slugify_strasse(strasse)
    hausnr = (hausnr or "").strip()
    if hausnr:
        address_part = f"{strasse_slug}+{quote(hausnr)},+{plz}"
    else:
        address_part = f"{strasse_slug},+{plz}"
    return (
        f"https://www.homeday.de/de/preisatlas/{stadt_slug}/{address_part}"
        f"?map_layer=standard&marketing_type={marketing_type}"
        f"&property_type={property_type}"
    )
