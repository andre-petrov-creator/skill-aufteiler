"""Parse a rendered ImmoScout24 expose page into structured data."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_KEYVALUES_PATTERNS = (
    re.compile(r"\bkeyValues\s*=\s*\{", re.DOTALL),
    re.compile(r"\bvar\s+keyValues\s*=\s*\{", re.DOTALL),
    re.compile(r"\bconst\s+keyValues\s*=\s*\{", re.DOTALL),
    re.compile(r"\blet\s+keyValues\s*=\s*\{", re.DOTALL),
)


def extract_keyvalues(html: str) -> Optional[Dict[str, Any]]:
    """Find `keyValues = {...}` in the HTML, brace-match, parse as JSON.

    Returns None when the marker is missing or parsing fails.
    """
    for pattern in _KEYVALUES_PATTERNS:
        match = pattern.search(html)
        if not match:
            continue
        # match.end() - 1 points at the opening brace
        start = match.end() - 1
        depth = 0
        for i in range(start, len(html)):
            ch = html[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = html[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
        # if we fell through, try next pattern
    return None


_HEATING_MAP = {
    "gas_heating": "Gas",
    "oil_heating": "Öl",
    "district_heating": "Fernwärme",
    "electric_heating": "Strom",
    "heat_pump": "Wärmepumpe",
    "wood_pellet_heating": "Holzpellets",
    "no_information": None,
}

_CONDITION_MAP = {
    "first_time_use": "Erstbezug",
    "first_time_use_after_refurbishment": "Erstbezug nach Sanierung",
    "mint_condition": "neuwertig",
    "refurbished": "saniert",
    "modernized": "modernisiert",
    "well_kept": "gepflegt",
    "need_of_renovation": "renovierungsbedürftig",
    "dilapidated": "abbruchreif",
    "no_information": None,
}

_OBJECT_TYPE_MAP = {
    "haus_kauf": "Haus",
    "wohnung_kauf": "Wohnung",
    "grundstueck_kauf": "Grundstück",
}


def decode_street_from_telekom_param(value: Optional[str]) -> Optional[Dict[str, str]]:
    """The obj_telekomInternetUrlAddition field is a base64-encoded JSON
    with keys ort, ortsteil, strasse, hausnummer. Decode it; return None on any failure.
    """
    if not value:
        return None
    try:
        # base64 may need padding fix
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(padded, validate=False)
        data = json.loads(decoded.decode("utf-8"))
        if not isinstance(data, dict):
            return None
        return {k: str(v) for k, v in data.items() if v is not None}
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "no_information"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    f = _to_float(value)
    return int(f) if f is not None else None


def _extract_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        return re.sub(r"\s*-\s*ImmobilienScout24\s*$", "", title)
    return ""


def _extract_image_urls(html: str) -> list:
    """Pull image URLs from the gallery. ImmoScout uses pictures.immobilienscout24.de."""
    pattern = re.compile(
        r'https://pictures\.immobilienscout24\.de/listings/[^"\'\s<>]+\.(?:jpg|jpeg|png|webp)',
        re.IGNORECASE,
    )
    seen: set = set()
    out: list = []
    for match in pattern.finditer(html):
        url = match.group(0)
        base = url.split("?")[0]
        if base not in seen:
            seen.add(base)
            out.append({"datei": None, "titel": None, "url_original": url})
    return out


# Anchors: each entry is a list of class-name fragments to look for.
# ImmoScout renders text sections as <pre class="is24qa-<section> ...">...</pre>
# but may also use id="is24qa-..." or data-qa="..." on some page versions.
_TEXT_SECTION_IDS = {
    "objektbeschreibung": [
        r'class="[^"]*is24qa-objektbeschreibung[^"]*"',
        r'id="is24qa-objektbeschreibung"',
        r'data-qa="objektbeschreibung"',
    ],
    "ausstattung": [
        r'class="[^"]*is24qa-ausstattung[^"]*"',
        r'id="is24qa-ausstattung"',
        r'data-qa="ausstattung"',
    ],
    "lage": [
        r'class="[^"]*is24qa-lage[^"]*"',
        r'id="is24qa-lage"',
        r'data-qa="lage"',
    ],
    "sonstiges": [
        r'class="[^"]*is24qa-sonstiges[^"]*"',
        r'id="is24qa-sonstiges"',
        r'data-qa="sonstiges"',
    ],
}


def _extract_section_text(html: str, anchors: list) -> str:
    """Find a section by any of the anchor regexes, then capture its inner text."""
    for anchor in anchors:
        # Match any tag that carries the anchor attribute/class
        pattern = re.compile(
            rf'<[^>]+{anchor}[^>]*>(.*?)</(?:pre|div|p|span|section)>',
            re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(html)
        if not match:
            continue
        raw = match.group(1)
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text
    return ""


def _extract_texte(html: str) -> Dict[str, str]:
    return {
        section: _extract_section_text(html, anchors)
        for section, anchors in _TEXT_SECTION_IDS.items()
    }


def _extract_anbieter(html: str) -> Dict[str, Optional[str]]:
    """Find provider name from the contact block.

    ImmoScout uses data-qa="contactName" for both private sellers and agencies.
    Agency pages may split into data-qa="contactName-company" and "contactName-name".
    """
    result: Dict[str, Optional[str]] = {
        "firma": None, "ansprechpartner": None, "telefon": None,
        "email": None, "anschrift": None,
    }
    # Agency: company name
    m = re.search(r'data-qa="contactName-company"[^>]*>([^<]+)<', html)
    if m:
        result["firma"] = m.group(1).strip()
    # Agency: contact person
    m = re.search(r'data-qa="contactName-name"[^>]*>([^<]+)<', html)
    if m:
        result["ansprechpartner"] = m.group(1).strip()
    # Private seller / fallback: single contactName field
    if not result["firma"] and not result["ansprechpartner"]:
        m = re.search(r'data-qa="contactName"[^>]*>([^<]+)<', html)
        if m:
            result["ansprechpartner"] = m.group(1).strip()
    # Phone
    m = re.search(r'href="tel:([^"]+)"', html)
    if m:
        result["telefon"] = m.group(1).strip()
    return result


def parse_expose(*, html: str, final_url: str) -> Dict[str, Any]:
    """Build the expose.json structure from rendered HTML."""
    kv = extract_keyvalues(html) or {}

    scout_id = kv.get("obj_scoutId") or kv.get("obj_objectnumber") or ""

    # address
    address_decoded = decode_street_from_telekom_param(kv.get("obj_telekomInternetUrlAddition"))
    strasse = None
    hausnummer = None
    if address_decoded:
        strasse = address_decoded.get("strasse") or None
        hausnummer = address_decoded.get("hausnummer") or None
    if not strasse and kv.get("obj_streetPlain") and kv["obj_streetPlain"] != "no_information":
        strasse = kv["obj_streetPlain"]
    if not hausnummer and kv.get("obj_houseNumber") and kv["obj_houseNumber"] != "no_information":
        hausnummer = kv["obj_houseNumber"]

    def _norm(val: Optional[str]) -> Optional[str]:
        if not val or val == "no_information":
            return None
        return val.replace("_", " ").title()

    adresse = {
        "strasse": strasse,
        "hausnummer": hausnummer,
        "plz": kv.get("obj_zipCode") or None,
        "ort": _norm(kv.get("geo_krs") or kv.get("obj_regio2")),
        "stadtteil": _norm(kv.get("geo_ot") or kv.get("obj_regio4")),
        "land": "DE",
        "lat": None,
        "lng": None,
    }

    energy_type = kv.get("obj_energyType", "")
    eckdaten = {
        "objektart": _OBJECT_TYPE_MAP.get(kv.get("obj_immotype", ""), kv.get("obj_immotype")),
        "kaufpreis_eur": _to_int(kv.get("obj_purchasePrice")),
        "wohnflaeche_qm": _to_float(kv.get("obj_livingSpace")),
        "nutzflaeche_qm": None,
        "grundstuecksflaeche_qm": _to_float(kv.get("obj_lotArea")),
        "anzahl_zimmer": _to_float(kv.get("obj_noRooms")),
        "anzahl_wohneinheiten": None,
        "anzahl_gewerbeeinheiten": None,
        "baujahr": _to_int(kv.get("obj_yearConstructed")),
        "modernisierung_jahr": _to_int(kv.get("obj_lastRefurbish")),
        "zustand": _CONDITION_MAP.get(kv.get("obj_condition", ""), kv.get("obj_condition")),
        "ausstattung_stufe": kv.get("obj_interiorQual") if kv.get("obj_interiorQual") != "no_information" else None,
        "etagen": _to_int(kv.get("obj_numberOfFloors")),
        "heizung": _HEATING_MAP.get(kv.get("obj_heatingType", ""), kv.get("obj_heatingType")),
        "energietraeger": kv.get("obj_firingTypes") if kv.get("obj_firingTypes") != "no_information" else None,
        "endenergiebedarf_kwh": _to_float(kv.get("obj_thermalChar")) if energy_type == "energy_requirement" else None,
        "endenergieverbrauch_kwh": _to_float(kv.get("obj_thermalChar")) if energy_type == "energy_consumption" else None,
        "energieausweistyp": (
            "Bedarfsausweis" if energy_type == "energy_requirement"
            else "Verbrauchsausweis" if energy_type == "energy_consumption"
            else None
        ),
        "energieeffizienzklasse": kv.get("obj_energyEfficiencyClass") if kv.get("obj_energyEfficiencyClass") not in (None, "no_information") else None,
        "befeuerung": _HEATING_MAP.get(kv.get("obj_firingTypes", ""), kv.get("obj_firingTypes")),
        "provision_prozent": None,
        "provision_eur": None,
        "mieteinnahmen_jahr_eur": None,
        "kaltmiete_pro_qm": None,
    }

    courtage = kv.get("obj_courtage", "")
    if courtage and courtage != "n":
        eckdaten["provision_prozent"] = _to_float(courtage)

    bilder = _extract_image_urls(html)

    return {
        "scraper_version": "1.0",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "final_url": final_url,
        "scout_id": scout_id,
        "successful_stage": None,
        "stages_attempted": [],
        "ueberschrift": _extract_title(html),
        "adresse": adresse,
        "eckdaten": eckdaten,
        "wohneinheiten": [],
        "texte": _extract_texte(html),
        "anbieter": _extract_anbieter(html),
        "bilder": bilder,
        "raw_keyvalues_path": "expose_keyvalues.json",
    }
