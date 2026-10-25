"""
m01_boris_brw.py — BORIS.NRW Bodenrichtwert-Abruf via offizieller OGC-Schnittstelle.

Tool für Modul 1 (skills/aufteiler-modul-1-objektbasis). Geocodiert die Adresse
über den BKG-Ortssuche-Service und holt den BRW per WMS GetFeatureInfo
(application/geo+json) gegen `wms.nrw.de/boris/wms_nw_brw` — der offizielle
OGC-konforme Pfad. Liefert beide MFH-relevanten Nutzungsarten
(Ein/zweigeschossig + Misch-/Mehrgeschossig). Primärwert für MFH =
Misch-/Mehrgeschossig.

Endpoints:
- gdz_ortssuche/geosearch                       → Adresse → X/Y (EPSG:25832), BKG
- wms.nrw.de/boris/wms_nw_brw (GetFeatureInfo)  → X/Y → BRW, OGC WMS 1.3.0

Layer-Mapping (Datenmodell BORIS-NRW v4.1):
- Layer "17" = brw_mehrgeschossige_bauweise  (Nutzungs-Code "2", MFH-Primärwert)
- Layer "20" = brw_ein_zweigeschossig        (Nutzungs-Code "1")

Output: JSON auf stdout, Logs auf stderr.
Exit-Codes:
  0 = erfolgreich, BRW im JSON
  1 = Adresse nicht in NRW / kein BRW-Datenraum / Endpoint-Fehler
  2 = Adresse mehrdeutig oder Hausnummer nicht eindeutig — JSON enthält `kandidaten`

CLI:
    python tools/m01_boris_brw.py \
        --strasse "Deutsche Straße" --hausnr 59 \
        --plz 44339 --ort "Dortmund"

    # Nur Geocoding ohne BRW-Call — für den Sub-Pfad 2a.3a in Modul 1
    # (User hat in der Adress-Bestätigung "Andere Adresse" gewählt):
    python tools/m01_boris_brw.py \
        --strasse "Prosperstraße" --hausnr 59 \
        --plz 45356 --ort "Essen" --mode geocode-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any

import httpx

ENDPOINT_GEOSEARCH = "https://www.gis-rest.nrw.de/bkg/gdz_ortssuche/geosearch"
ENDPOINT_WMS_BRW = "https://www.wms.nrw.de/boris/wms_nw_brw"

# Nutzungs-Code (interne API) → WMS-Layer-ID (Datenmodell BORIS-NRW v4.1)
LAYER_FOR_NUTZUNG = {
    "1": "20",  # Ein/zweigeschossig
    "2": "17",  # Misch-/Mehrgeschossig (MFH-Primärwert)
}

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "de-DE,de;q=0.9",
    "Referer": "https://www.boris.nrw.de/boris-nrw/index.html?lang=de",
}

# Validierungs-Schwelle: unter 2.0 ist geosearch ein Fuzzy-Treffer
# (z.B. "Hugo-Erfurt-Straße in Wuppertal" für "Hauptstraße Erfurt" liefert 1.5)
MIN_SCORE = 2.0

NUTZUNGSARTEN = {
    "1": "Ein/zweigeschossig",
    "2": "Misch-/Mehrgeschossig",
}

# Code-Tabellen aus BORIS-NRW Datenmodell — nur dokumentierte Codes;
# unbekannte werden roh durchgereicht.
ENTW_NAMEN = {
    "B": "Baureifes Land",
    "R": "Rohbauland",
    "BE": "Bauerwartungsland",
    "LF": "Fläche der Land- und Forstwirtschaft",
    "SO": "Sonstige Fläche",
}
NUTA_NAMEN = {
    "W": "Wohnbaufläche",
    "M": "Gemischte Baufläche",
    "G": "Gewerbliche Baufläche",
    "S": "Sonderbaufläche",
}


def log(msg: str) -> None:
    print(f"[BRW] {msg}", file=sys.stderr, flush=True)


def _normalize_street(s: str | None) -> str:
    """
    Normalisiert Straßennamen für Vergleich.

    "Prosperstraße"  → "prosperstr"
    "Prosperstr."    → "prosperstr"
    "Prosperstrasse" → "prosperstr"
    "Deutsche Straße"→ "deutsche str"
    """
    s = (s or "").lower().strip()
    # Reihenfolge wichtig: längste Form zuerst, damit "straße" nicht erst "strae" wird
    for needle in ("straße", "strasse", "str."):
        s = s.replace(needle, "str")
    return " ".join(s.split())


def _plz_is_nrw(plz: str | int) -> bool:
    """
    Heuristik: liegt die PLZ im NRW-Bereich (32xxx–37xxx, 40xxx–53xxx, 57xxx–59xxx)?
    Grenzfälle wie 53 (teils RLP) oder 57 (teils RLP) werden als NRW akzeptiert —
    geosearch + bundesland-Check fängt Reststreuung ab. Nicht-parsbare PLZ
    werden defensiv durchgelassen.
    """
    try:
        n = int(str(plz).strip())
    except (ValueError, TypeError):
        return True
    return (32000 <= n <= 37999) or (40000 <= n <= 53999) or (57000 <= n <= 59999)


def _features_summary(features: list[dict[str, Any]], n: int = 5) -> list[dict[str, Any]]:
    out = []
    for f in features[:n]:
        p = f.get("properties", {}) or {}
        out.append(
            {
                "text": p.get("text"),
                "typ": p.get("typ"),
                "score": p.get("score"),
                "plz": p.get("plz"),
                "ort": p.get("ort"),
                "ortsteil": p.get("ortsteil"),
                "bundesland": p.get("bundesland"),
            }
        )
    return out


def geocode(
    client: httpx.Client,
    strasse: str,
    hausnr: str,
    plz: str,
    ort: str,
) -> dict[str, Any]:
    """
    Geocodiert die Adresse über gdz_ortssuche/geosearch.

    Returns dict with key `status`:
      "ok"        → enthält x, y, bestaetigte_adresse, ortsteil, plz_found, ort_found
      "notfound"  → keine Treffer
      "outside"   → erster Treffer außerhalb NRW (sollte mit Filter nicht passieren, defensiv)
      "ambiguous" → Hausnummer-/PLZ-/Score-Validierung fehlgeschlagen, enthält `kandidaten`
    """
    query = f"{strasse} {hausnr}, {plz} {ort}".strip()
    params = {
        "outputformat": "json",
        "count": 5,
        "filter": "bundesland:Nordrhein-Westfalen",
        "query": query,
        "srsName": "EPSG:25832",
    }

    log(f"geosearch query: {query}")
    r = client.get(ENDPOINT_GEOSEARCH, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    features = data.get("features") or []
    log(f"geosearch hits: {len(features)}")

    if not features:
        return {"status": "notfound", "query": query}

    f0 = features[0]
    props = f0.get("properties") or {}

    if props.get("bundesland") != "Nordrhein-Westfalen":
        return {
            "status": "outside",
            "query": query,
            "gefunden": props.get("text"),
            "bundesland": props.get("bundesland"),
        }

    if props.get("typ") != "Haus":
        return {
            "status": "ambiguous",
            "reason": f"Hausnummer nicht eindeutig (typ='{props.get('typ')}', erwartet 'Haus')",
            "query": query,
            "kandidaten": _features_summary(features),
        }

    # Straßen-Match prüfen BEVOR Score-Filter — sonst akzeptiert man
    # z.B. "Erdwegstr. 59, 45356 Essen" (Score 2.04) für eine Anfrage
    # "Prosperstraße 59, 45356 Essen" (existiert nicht in 45356).
    found_strasse = props.get("strasse")
    if _normalize_street(found_strasse) != _normalize_street(strasse):
        return {
            "status": "ambiguous",
            "reason": (
                f"Straßen-Mismatch: angefragt {strasse!r}, gefunden {found_strasse!r} "
                f"in {props.get('plz')} {props.get('ort')}"
            ),
            "query": query,
            "kandidaten": _features_summary(features),
        }

    score = props.get("score") or 0.0
    if score < MIN_SCORE:
        return {
            "status": "ambiguous",
            "reason": f"Treffer-Score zu niedrig ({score:.2f} < {MIN_SCORE}) — vermutlich Fuzzy-Match auf abweichende Adresse",
            "query": query,
            "kandidaten": _features_summary(features),
        }

    if plz and str(props.get("plz") or "") != str(plz):
        return {
            "status": "ambiguous",
            "reason": f"PLZ-Mismatch: angefragt {plz}, gefunden {props.get('plz')} ({props.get('text')})",
            "query": query,
            "kandidaten": _features_summary(features),
        }

    coords = (f0.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return {
            "status": "notfound",
            "query": query,
            "reason": "Treffer ohne Koordinaten",
        }

    return {
        "status": "ok",
        "x": float(coords[0]),
        "y": float(coords[1]),
        "bestaetigte_adresse": props.get("text"),
        "ort_found": props.get("ort"),
        "ortsteil": props.get("ortsteil"),
        "plz_found": props.get("plz"),
        "score": score,
    }


def _to_int_or_none(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _clean_str(v: Any) -> str | None:
    """Whitespace-strip + leerer String → None (BORIS-Datensätze nutzen ' ' für 'kein Wert')."""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _decode_wms(content: bytes) -> str:
    """
    WMS-Server liefert UTF-8-encoded JSON (Content-Type deklariert es korrekt).
    Default-Decode ist ausreichend. Wrapper bleibt für künftige Encoding-Fixes.
    """
    return content.decode("utf-8")


def fetch_brw_for_nutzung(
    client: httpx.Client,
    x: float,
    y: float,
    nutzung: str,
) -> dict[str, Any] | None:
    """
    Holt BRW für EINE Nutzungsart an gegebener Koordinate (EPSG:25832) per
    offizieller WMS GetFeatureInfo (application/geo+json).

    Returns None, wenn keine BRW-Zone an dem Punkt für diese Nutzungsart liegt.
    Returns dict mit allen für Modul 1 relevanten Feldern, sonst.

    WMS GetFeatureInfo liefert nur den aktuellen Wert der Zone (keine Zeitreihe).
    Stichtag aus der Property STAG entspricht der jährlichen BRW-Festsetzung.
    """
    layer = LAYER_FOR_NUTZUNG.get(nutzung)
    if not layer:
        return None

    # 1m × 1m-Bbox um den Punkt, 101 × 101 Pixel — I=J=50 trifft die Koordinate.
    bbox = f"{x-50},{y-50},{x+50},{y+50}"
    params = {
        "SERVICE": "WMS",
        "VERSION": "1.3.0",
        "REQUEST": "GetFeatureInfo",
        "LAYERS": layer,
        "QUERY_LAYERS": layer,
        "BBOX": bbox,
        "WIDTH": "101",
        "HEIGHT": "101",
        "CRS": "EPSG:25832",
        "I": "50",
        "J": "50",
        "INFO_FORMAT": "application/geo+json",
        "FEATURE_COUNT": "5",
    }

    r = client.get(ENDPOINT_WMS_BRW, params=params, timeout=20)
    r.raise_for_status()
    data = json.loads(_decode_wms(r.content))

    features = data.get("features") or []
    log(f"WMS layer={layer} (nutzung={nutzung}): {len(features)} features")
    if not features:
        return None

    p = features[0].get("properties") or {}
    brw_int = _to_int_or_none(p.get("BRW"))
    if brw_int is None or brw_int <= 0:
        return None

    nuta_code = (_clean_str(p.get("NUTA")) or "").strip()
    entw_code = (_clean_str(p.get("ENTW")) or "").strip()

    return {
        "nutzungsart_code": nutzung,
        "nutzungsart": NUTZUNGSARTEN.get(nutzung, f"nutzung={nutzung}"),
        "brw_eur_pro_qm": brw_int,
        "stichtag": _clean_str(p.get("STAG")),
        "hbrw_eur_pro_qm": _to_int_or_none(p.get("HBRW")),
        "hauptfeststellungs_stichtag": _clean_str(p.get("HTAG")),
        "bodenrichtwertnummer": _clean_str(p.get("WNUM")),
        "brw_zonennummer": _clean_str(p.get("BRWZNR")),
        "gemeinde": _clean_str(p.get("GENA")),
        "gemarkung": _clean_str(p.get("GEMA")),
        "ortsteil": _clean_str(p.get("ORTST")),
        "plz": _clean_str(p.get("PLZ")),
        "geschosszahl": _clean_str(p.get("GEZ")),
        "flaeche": _clean_str(p.get("FLAE")),
        "tiefe": _clean_str(p.get("GTIE")),
        "nutzungsart_text": NUTA_NAMEN.get(nuta_code, nuta_code or None),
        "entwicklungszustand_code": entw_code or None,
        "entwicklungszustand": ENTW_NAMEN.get(entw_code, entw_code or None),
        "beitragszustand_code": _clean_str(p.get("BEIT")),
        "gutachterausschuss": _clean_str(p.get("GABE")),
        "datenblatt_url": _clean_str(p.get("UDOK_URL")),
        "zeitreihe_anzahl": None,  # WMS GetFeatureInfo liefert keine Zeitreihe (nur aktuelle Festsetzung)
    }


def fetch_brw(
    strasse: str,
    hausnr: str,
    plz: str,
    ort: str,
) -> tuple[dict[str, Any], int]:
    """
    Komplett-Workflow. Returns (json_payload, exit_code).
    """
    adresse_in = f"{strasse} {hausnr}, {plz} {ort}".strip()

    # Pre-Validation: PLZ außerhalb NRW-Bereichs → ohne API-Call abbrechen.
    # geosearch würde sonst Fuzzy-Treffer in NRW liefern, was den User verwirrt.
    if plz and not _plz_is_nrw(plz):
        return (
            {
                "error": "Adresse außerhalb NRW",
                "adresse": adresse_in,
                "grund": f"PLZ {plz} liegt nicht im NRW-Bereich (32xxx–37xxx, 40xxx–53xxx, 57xxx–59xxx)",
            },
            1,
        )

    with httpx.Client(headers=HTTP_HEADERS, follow_redirects=True, timeout=20) as client:
        try:
            geo = geocode(client, strasse, hausnr, plz, ort)
        except httpx.HTTPError as exc:
            return (
                {
                    "error": f"Geocoding-Endpoint nicht erreichbar: {exc}",
                    "endpoint": ENDPOINT_GEOSEARCH,
                    "adresse": adresse_in,
                },
                1,
            )

        if geo["status"] == "notfound":
            return (
                {
                    "error": "Adresse nicht in NRW gefunden",
                    "adresse": adresse_in,
                    "details": geo.get("reason"),
                },
                1,
            )
        if geo["status"] == "outside":
            return (
                {
                    "error": "Adresse außerhalb NRW",
                    "adresse": adresse_in,
                    "gefunden": geo.get("gefunden"),
                    "bundesland_gefunden": geo.get("bundesland"),
                },
                1,
            )
        if geo["status"] == "ambiguous":
            return (
                {
                    "error": "Adresse mehrdeutig oder Hausnummer nicht eindeutig",
                    "adresse": adresse_in,
                    "grund": geo.get("reason"),
                    "kandidaten": geo.get("kandidaten") or [],
                },
                2,
            )

        # status == "ok"
        nutz_results: list[dict[str, Any]] = []
        for nutzung in ("1", "2"):
            try:
                r = fetch_brw_for_nutzung(client, geo["x"], geo["y"], nutzung)
            except httpx.HTTPError as exc:
                log(f"BRW-Call nutzung={nutzung} failed: {exc}")
                continue
            if r:
                nutz_results.append(r)

        if not nutz_results:
            return (
                {
                    "error": "Keine BRW-Zone für diese Koordinate gefunden",
                    "adresse": adresse_in,
                    "bestaetigte_adresse": geo["bestaetigte_adresse"],
                    "koordinaten_epsg25832": [geo["x"], geo["y"]],
                },
                1,
            )

        # MFH-Primärwert = Misch-/Mehrgeschossig falls vorhanden, sonst erstes Ergebnis
        primary = next(
            (r for r in nutz_results if r["nutzungsart_code"] == "2"),
            nutz_results[0],
        )

        payload = {
            "adresse_eingabe": adresse_in,
            "bestaetigte_adresse": geo["bestaetigte_adresse"],
            "brw_eur_pro_qm": primary["brw_eur_pro_qm"],
            "nutzungsart": primary["nutzungsart"],
            "stichtag": primary["stichtag"],
            "bodenrichtwertnummer": primary["bodenrichtwertnummer"],
            "gemeinde": primary["gemeinde"],
            "gemarkung": primary["gemarkung"],
            "ortsteil": primary["ortsteil"],
            "plz": primary["plz"],
            "koordinaten_epsg25832": [geo["x"], geo["y"]],
            "geocoding_score": geo["score"],
            "alle_nutzungsarten": nutz_results,
            "quelle": "BORIS.NRW (gis-rest.nrw.de)",
            "abgerufen_am": date.today().isoformat(),
        }
        return payload, 0


def fetch_candidates(
    strasse: str,
    hausnr: str,
    plz: str,
    ort: str,
) -> tuple[dict[str, Any], int]:
    """
    Geocode-only-Variante: macht geosearch und gibt features[0..4] mit Koordinaten
    als gleichwertige Liste zurück. KEIN BRW-Lookup, KEINE Validierungs-Kaskade
    (kein Score/Straßen/PLZ-Filter) — der User pickt selbst, das ist der
    Validierungspunkt im Sub-Pfad 2a.3a von Modul 1.

    PLZ-NRW-Pre-Check bleibt erhalten (verhindert sinnlose Calls außerhalb NRW).

    Returns (payload, exit_code):
      0 — mindestens 1 Treffer, JSON mit
          `kandidaten: [{text, typ, score, strasse, hausnr, plz, ort, ortsteil,
          bundesland, x, y}]` (max 5).
      1 — kein Treffer / außerhalb NRW / Endpoint-Fehler.
    """
    adresse_in = f"{strasse} {hausnr}, {plz} {ort}".strip()

    if plz and not _plz_is_nrw(plz):
        return (
            {
                "error": "Adresse außerhalb NRW",
                "adresse": adresse_in,
                "grund": f"PLZ {plz} liegt nicht im NRW-Bereich (32xxx–37xxx, 40xxx–53xxx, 57xxx–59xxx)",
            },
            1,
        )

    query = f"{strasse} {hausnr}, {plz} {ort}".strip()
    params = {
        "outputformat": "json",
        "count": 5,
        "filter": "bundesland:Nordrhein-Westfalen",
        "query": query,
        "srsName": "EPSG:25832",
    }

    with httpx.Client(headers=HTTP_HEADERS, follow_redirects=True, timeout=20) as client:
        try:
            log(f"geocode-only query: {query}")
            r = client.get(ENDPOINT_GEOSEARCH, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            return (
                {
                    "error": f"Geocoding-Endpoint nicht erreichbar: {exc}",
                    "endpoint": ENDPOINT_GEOSEARCH,
                    "adresse": adresse_in,
                },
                1,
            )

    features = data.get("features") or []
    log(f"geocode-only hits: {len(features)}")

    if not features:
        return (
            {
                "error": "Keine Treffer in NRW",
                "adresse": adresse_in,
            },
            1,
        )

    kandidaten: list[dict[str, Any]] = []
    for f in features[:5]:
        p = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or []
        kandidaten.append(
            {
                "text": p.get("text"),
                "typ": p.get("typ"),
                "score": p.get("score"),
                "strasse": p.get("strasse"),
                "hausnr": p.get("hausnr"),
                "plz": p.get("plz"),
                "ort": p.get("ort"),
                "ortsteil": p.get("ortsteil"),
                "bundesland": p.get("bundesland"),
                "x": float(coords[0]) if len(coords) >= 2 else None,
                "y": float(coords[1]) if len(coords) >= 2 else None,
            }
        )

    return (
        {
            "mode": "geocode-only",
            "adresse_eingabe": adresse_in,
            "kandidaten": kandidaten,
            "quelle": "BORIS.NRW (gis-rest.nrw.de)",
            "abgerufen_am": date.today().isoformat(),
        },
        0,
    )


def main() -> None:
    # Windows: stdout default ist cp1252 wenn stdout=pipe. JSON mit Umlauten
    # (Straße, Gemarkungsname) bricht dann. Erzwingen: UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="BORIS.NRW Bodenrichtwert-Abruf via REST",
    )
    parser.add_argument("--strasse", required=True)
    parser.add_argument("--hausnr", required=True)
    parser.add_argument("--plz", required=True)
    parser.add_argument("--ort", required=True)
    parser.add_argument(
        "--mode",
        choices=["full", "geocode-only"],
        default="full",
        help=(
            "full (default): Geocoding + Validierungs-Kaskade + BRW-Lookup. "
            "geocode-only: nur geosearch, features[0..4] mit Koordinaten als "
            "gleichwertige Kandidatenliste (für Sub-Pfad 2a.3a in Modul 1, "
            "wenn der User 'Andere Adresse' wählt). Kein BRW-Call."
        ),
    )
    parser.add_argument(
        "--jahrgang",
        type=int,
        default=date.today().year,
        help="reserviert für v1.1 (Stichtag-Wahl). v1 liefert immer den aktuellsten Stichtag.",
    )
    # Deprecated, von alten Aufrufern toleriert:
    parser.add_argument("--headless", action="store_true", help="(deprecated, no-op)")
    parser.add_argument("--debug", action="store_true", help="(deprecated, no-op; Logs gehen immer auf stderr)")
    args = parser.parse_args()

    if args.headless or args.debug:
        log("Hinweis: --headless / --debug sind deprecated (REST-Pfad, kein Browser mehr).")

    try:
        if args.mode == "geocode-only":
            result, exit_code = fetch_candidates(
                strasse=args.strasse,
                hausnr=str(args.hausnr),
                plz=str(args.plz),
                ort=args.ort,
            )
        else:
            result, exit_code = fetch_brw(
                strasse=args.strasse,
                hausnr=str(args.hausnr),
                plz=str(args.plz),
                ort=args.ort,
            )
    except Exception as exc:  # defensive Schutz-Catch
        result = {
            "error": f"Unerwarteter Fehler: {exc.__class__.__name__}: {exc}",
            "adresse": f"{args.strasse} {args.hausnr}, {args.plz} {args.ort}",
        }
        exit_code = 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
