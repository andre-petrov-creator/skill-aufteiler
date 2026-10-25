"""Immometrica-Adapter — Marktstatistik via nodriver (Anti-Detect Chrome).

Liefert 4 Stat-Bloecke pro Adresse:
- PLZ / ETW (mit Zusatzinfo Wohnung mieten)
- PLZ / Hauskauf + Mehrfamilienhaus (mit Zusatzinfo Haus mieten)
- Stadt / ETW (mit Zusatzinfo Wohnung mieten)
- Stadt / Hauskauf + Mehrfamilienhaus (mit Zusatzinfo Haus mieten)

Login wird via persistiertem User-Data-Dir wiederverwendet. Falls Session
abgelaufen ist, faellt das Skript zurueck auf Auto-Login mit .env-Credentials.

Output (JSON, kompatibel zu RunResult-Schema, alle Spezifika im extra-Slot):
{
  "status": "ok"|"error",
  "portal": "immometrica",
  "marktwert_eur_mittel": null,
  "marktwert_eur_min": null,
  "marktwert_eur_max": null,
  "trends": {...},
  "trend_ampel": null,
  "trend_label": null,
  "url": "https://www.immometrica.com/de/statistics",
  "timestamp": "<iso>",
  "screenshot_path": null,
  "extra": {
    "year_half": "H1/2026",
    "plz_input": "45357",
    "stadt_input": "Essen",
    "plz_etw": {"uebersicht": {...}, "zusatzinfo": {...}},
    "plz_mfh": {"uebersicht": {...}, "zusatzinfo": {...}},
    "stadt_etw": {"uebersicht": {...}, "zusatzinfo": {...}},
    "stadt_mfh": {"uebersicht": {...}, "zusatzinfo": {...}}
  }
}

AENDERUNGEN 2026-09-10 (Login-Fix nach Totalausfall):
- `_do_login` auf das neue v2-Login-Formular umgestellt: Direkt-Navigation auf
  URL_LOGIN + Selektoren (`[data-testid="v2-login-submit"]`) statt Text-Suche.
  Ursache des Ausfalls: `tab.find("Login")` traf das E-Mail-Feld (`id="id_login"`),
  `tab.find("Anmelden")` die `<h1>`-Ueberschrift — kein Submit, aber `return True`.
  Folge: der Adapter arbeitete auf der Login-Seite weiter, alle sechs Configs
  endeten in `submit_button_not_found` → `all_configs_failed`.
- `_do_login` verifiziert den Login jetzt (`_wait_for_login_confirmed`) statt
  bedingungslos `True` zu liefern.
- "Angemeldet bleiben" (`#id_remember`) wird gesetzt, damit die Session im
  persistenten User-Data-Dir zwischen Laeufen ueberdauert.
- Blinde Sleeps im Login durch Polling ersetzt (`_wait_for_login_form`).
- `_run_async` bricht mit `session_lost` / `statistics_form_not_ready` ab, wenn
  das Marktstatistik-Formular nicht laedt, statt sechs Configs blind
  durchzuklicken und einen irrefuehrenden Fehler zu melden.
- Heading-Diff-Check (v3.3, `_wait_for_stat_heading` + `_RADIO_TO_EXPECTED_HEADING`)
  unveraendert.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from portals.immometrica.parsers import parse_stat_block, parse_geo_state

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent.parent
RUNS_DIR = PROJ_ROOT / "runs"
STATE_DIR = PROJ_ROOT / "learned_selectors"
USER_DATA_DIR = STATE_DIR / "immometrica_nodriver_userdata"
BERLIN_TZ = timezone(timedelta(hours=2))

URL_STATISTICS = "https://www.immometrica.com/de/statistics"
URL_HOME = "https://www.immometrica.com/de/home"
URL_LOGIN = "https://www.immometrica.com/de/accounts/login/?next=/de/home"

# Submit-Button des v2-Login-Formulars (`data-testid="v2-login-form"`).
# Testid zuerst, semantischer Anker als Rueckfall.
_LOGIN_SUBMIT_SELECTORS = (
    '[data-testid="v2-login-submit"]',
    'form.auth-form button[type="submit"]',
)


def _ts_iso() -> str:
    return datetime.now(BERLIN_TZ).isoformat()


def _ts_slug() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _load_env_creds() -> tuple[Optional[str], Optional[str]]:
    env_path = PROJ_ROOT / ".env"
    if not env_path.exists():
        return os.environ.get("IMMOMETRICA_USERNAME"), os.environ.get("IMMOMETRICA_PASSWORD")
    user = pw = None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "IMMOMETRICA_USERNAME":
            user = v
        elif k == "IMMOMETRICA_PASSWORD":
            pw = v
    return user, pw


async def _eval_str(tab, expression: str) -> str:
    """tab.evaluate auf String reduziert (nodriver liefert teils {'value': ...})."""
    try:
        v = await tab.evaluate(expression)
    except Exception:
        return ""
    if isinstance(v, dict) and "value" in v:
        v = v["value"]
    return v if isinstance(v, str) else ""


async def _login_state(tab) -> tuple[str, bool]:
    """(url, logged_in) — eingeloggt gilt nur mit App-Navigation UND ohne Login-Route.

    Der URL-Teil ist entscheidend: die Login-Seite selbst enthaelt kein
    'Logout'/'Profil', aber ein Redirect auf /de/accounts/login/ ist der
    eindeutige Beleg, dass die Session weg ist.
    """
    url = await _eval_str(tab, "document.location.href")
    body = await _eval_str(tab, "(document.body && document.body.innerText) || ''")
    logged_in = (
        "/accounts/login" not in url
        and ("Logout" in body or "Profil" in body)
    )
    return url, logged_in


async def _wait_for_login_form(tab, timeout_s: float = 15.0):
    """Pollt auf E-Mail- + Passwort-Feld des v2-Formulars statt blind zu schlafen."""
    import time
    deadline = time.monotonic() + timeout_s
    while True:
        email_inp = await tab.query_selector('input[type="email"]')
        pw_inp = await tab.query_selector('input[type="password"]')
        if email_inp and pw_inp:
            return email_inp, pw_inp
        if time.monotonic() >= deadline:
            return None, None
        await asyncio.sleep(0.5)


async def _wait_for_login_confirmed(tab, timeout_s: float = 25.0) -> tuple[bool, str]:
    """Pollt bis die App-Session steht. Returns (logged_in, letzte_url)."""
    import time
    deadline = time.monotonic() + timeout_s
    url = ""
    while True:
        url, logged_in = await _login_state(tab)
        if logged_in:
            return True, url
        if time.monotonic() >= deadline:
            return False, url
        await asyncio.sleep(0.6)


async def _do_login(tab, user: str, pw: str,
                    verify_timeout_s: float = 25.0) -> bool:
    """Login gegen das v2-Formular (`data-testid="v2-login-form"`).

    Ursache des Totalausfalls vom 2026-09-10: Text-Suche ist auf diesem Formular
    untauglich. nodrivers `find("Login")` trifft das E-Mail-Feld (`id="id_login"` —
    die Suche greift auch auf Attributwerte), `find("Anmelden")` die
    `<h1 class="auth-title">`-Ueberschrift. Beide Klicks submitten nichts; das alte
    `_do_login` meldete trotzdem Erfolg, der Adapter lief auf der Login-Seite
    weiter und alle sechs Configs endeten in `submit_button_not_found`.

    Deshalb: Direkt-Navigation auf die Login-Route, Selektoren statt Text,
    und ein echter Erfolgs-Nachweis statt `return True`.
    """
    if not user or not pw:
        print(">>> _do_login: Credentials fehlen", file=sys.stderr, flush=True)
        return False
    try:
        await tab.get(URL_LOGIN)
        email_inp, pw_inp = await _wait_for_login_form(tab)
        if not email_inp or not pw_inp:
            print(">>> _do_login: v2-Login-Formular nicht gefunden",
                  file=sys.stderr, flush=True)
            return False

        await email_inp.click()
        await asyncio.sleep(0.3)
        await email_inp.send_keys(user)
        await pw_inp.click()
        await asyncio.sleep(0.3)
        await pw_inp.send_keys(pw)

        # "Angemeldet bleiben" — laesst die Session im persistenten User-Data-Dir
        # ueberdauern. Ohne das lief sie zwischen zwei Laeufen ab (Ausfall 2026-09-10).
        remember = await tab.query_selector("#id_remember")
        if remember:
            await remember.click()

        btn = None
        for sel in _LOGIN_SUBMIT_SELECTORS:
            btn = await tab.query_selector(sel)
            if btn:
                break
        if not btn:
            print(">>> _do_login: Submit-Button des Login-Formulars nicht gefunden",
                  file=sys.stderr, flush=True)
            return False

        await asyncio.sleep(0.5)
        await btn.click()

        logged_in, url = await _wait_for_login_confirmed(
            tab, timeout_s=verify_timeout_s
        )
        if not logged_in:
            print(f">>> _do_login: Login nicht bestaetigt (url={url!r})",
                  file=sys.stderr, flush=True)
        else:
            print(">>> _do_login: Login bestaetigt", file=sys.stderr, flush=True)
        return logged_in
    except Exception as e:
        print(f">>> _do_login Exception: {e}", file=sys.stderr, flush=True)
        return False


async def _ensure_logged_in(tab) -> bool:
    """Prueft ob Statistik-Page erreichbar ist (Persistent-Cookies aktiv).

    Falls nicht: Auto-Login mit .env-Credentials.
    """
    try:
        await tab.get(URL_STATISTICS)
        await asyncio.sleep(8.0)  # generoes - App-Hydration kann lange dauern
        _url, logged_in = await _login_state(tab)
        body = await _eval_str(tab, "(document.body && document.body.innerText) || ''")
        # Erfolgs-Indikator: "Statistik erstellen" Button + aktive App-Session
        if logged_in and "Statistik erstellen" in body:
            return True
    except Exception:
        pass
    # Login noetig
    user, pw = _load_env_creds()
    if not user or not pw:
        print(">>> WARN: .env Credentials fehlen", file=sys.stderr, flush=True)
        return False
    print(">>> Session abgelaufen, starte Auto-Login", file=sys.stderr, flush=True)
    return await _do_login(tab, user, pw)


async def _click_marktstatistik_sidebar(tab) -> bool:
    """Klickt den Marktstatistik-Link im linken Sidebar.

    Direkte URL-Navigation zu /de/statistics zerbricht React-Select
    (kein Suggestions-Trigger). Sidebar-Klick triggert die App-eigene
    Initialisierungs-Routine.
    """
    try:
        clicked = await tab.evaluate(
            """(() => {
                const links = Array.from(document.querySelectorAll('a, button'))
                    .filter(el => el.innerText.trim() === 'Marktstatistik');
                if (links.length === 0) return false;
                links[0].click();
                return true;
            })()"""
        )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        return bool(clicked)
    except Exception as e:
        print(f">>> _click_marktstatistik_sidebar Exception: {e}",
              file=sys.stderr, flush=True)
        return False


async def _wait_for_marktstatistik_ready(tab, timeout_s: float = 20.0) -> bool:
    """Polling-Wait bis die Marktstatistik-Form vollstaendig im DOM ist.

    Markers: `id_construction_year_0/1` (Baujahr-Filter), `id_type_0`
    (ETW-Radio), `.location-select-widget` (Ort-Widget).
    """
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        ready = await tab.evaluate(
            """!!document.getElementById('id_construction_year_0') &&
               !!document.getElementById('id_type_0') &&
               !!document.querySelector('.location-select-widget')"""
        )
        if isinstance(ready, dict) and "value" in ready:
            ready = ready["value"]
        if ready:
            return True
        await asyncio.sleep(0.5)
    print(f">>>   _wait_for_marktstatistik_ready: timeout {timeout_s}s",
          file=sys.stderr, flush=True)
    return False


def _calc_baujahr_bis(baujahr: int) -> int:
    """Baujahr-bis-Filter: max(1980, baujahr + 5).

    Siehe Memory [[immometrica-baujahr-filter]]:
    - Objekt-Baujahr <= 1980 -> Filter 1900-1980
    - Objekt-Baujahr  > 1980 -> Filter 1900-(baujahr+5)
    """
    return max(1980, int(baujahr) + 5)


async def _set_baujahr_range(tab, baujahr_von: int, baujahr_bis: int) -> bool:
    """Setzt Baujahr-Range im Bauliches-Tab.

    Deterministische IDs aus DOM-Inspektion 2026-05-19:
        <input id="id_construction_year_0" name="construction_year_0"> (von)
        <input id="id_construction_year_1" name="construction_year_1"> (bis)

    Polling-Wait (max 15 s) bis die Inputs im DOM sind — App-Hydration
    nach Sidebar-Klick kann lange dauern (IntercoolerJS-asynchron).
    """
    import time
    von_s, bis_s = str(int(baujahr_von)), str(int(baujahr_bis))

    # Polling: warte bis Inputs im DOM
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        present = await tab.evaluate(
            "!!document.getElementById('id_construction_year_0') && "
            "!!document.getElementById('id_construction_year_1')"
        )
        if isinstance(present, dict) and "value" in present:
            present = present["value"]
        if present:
            break
        await asyncio.sleep(0.5)
    else:
        print(">>>   _set_baujahr_range: Inputs nicht im DOM nach 15s",
              file=sys.stderr, flush=True)
        return False

    try:
        raw = await tab.evaluate(
            f"""(() => {{
                const VON = {json.dumps(von_s)};
                const BIS = {json.dumps(bis_s)};

                function setInputValue(inp, val) {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    nativeSetter.call(inp, val);
                    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                    inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                    inp.dispatchEvent(new Event('blur', {{bubbles: true}}));
                }}

                const inpVon = document.getElementById('id_construction_year_0');
                const inpBis = document.getElementById('id_construction_year_1');
                let vonSet = false, bisSet = false;
                if (inpVon) {{ setInputValue(inpVon, VON); vonSet = true; }}
                if (inpBis) {{ setInputValue(inpBis, BIS); bisSet = true; }}
                return JSON.stringify({{vonSet, bisSet,
                    vonRead: inpVon ? inpVon.value : null,
                    bisRead: inpBis ? inpBis.value : null}});
            }})()"""
        )
        if isinstance(raw, dict) and "value" in raw:
            raw = raw["value"]
        if not isinstance(raw, str):
            print(f">>>   _set_baujahr_range: unerwarteter Returntyp {type(raw)}: {raw!r}",
                  file=sys.stderr, flush=True)
            return False
        try:
            result = json.loads(raw)
        except Exception:
            print(f">>>   _set_baujahr_range: JSON-Parse fail: {raw[:200]!r}",
                  file=sys.stderr, flush=True)
            return False
        von_set = bool(result.get("vonSet"))
        bis_set = bool(result.get("bisSet"))
        print(f">>>   Baujahr-Range {von_s}-{bis_s}: "
              f"von={von_set}({result.get('vonRead')!r}) "
              f"bis={bis_set}({result.get('bisRead')!r})",
              file=sys.stderr, flush=True)
        return von_set and bis_set
    except Exception as e:
        print(f">>>   _set_baujahr_range Exception: {e}",
              file=sys.stderr, flush=True)
        return False


async def _select_period(tab, year_half: str) -> Optional[str]:
    """Klickt einen Halbjahres-Button. Returns den tatsaechlich geklickten Text.

    Wenn year_half == 'latest' oder None: nimmt automatisch den neuesten
    sichtbaren Halbjahr-Button (regex-match auf H[12]/YYYY, letzter wins).
    Sonst: klickt den Button mit exaktem Text-Match.
    """
    try:
        if not year_half or year_half == "latest":
            clicked = await tab.evaluate(
                """(() => {
                    const btns = Array.from(document.querySelectorAll('a, button'))
                        .filter(b => /^H[12]\\/\\d{4}$/.test(b.innerText.trim()));
                    if (btns.length === 0) return null;
                    const last = btns[btns.length - 1];
                    last.click();
                    return last.innerText.trim();
                })()"""
            )
        else:
            clicked = await tab.evaluate(
                f"""(() => {{
                    const btns = Array.from(document.querySelectorAll('a, button'))
                        .filter(b => b.innerText.trim() === {json.dumps(year_half)});
                    if (btns.length === 0) return null;
                    btns[0].click();
                    return btns[0].innerText.trim();
                }})()"""
            )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        return clicked if isinstance(clicked, str) else None
    except Exception:
        return None


async def _press_enter(tab) -> None:
    """Echter Enter-Key via CDP (send_keys('Enter') macht char-events, kein Enter)."""
    from nodriver import cdp
    await tab.send(cdp.input_.dispatch_key_event(
        "keyDown",
        key="Enter",
        code="Enter",
        windows_virtual_key_code=13,
        native_virtual_key_code=13,
    ))
    await asyncio.sleep(0.05)
    await tab.send(cdp.input_.dispatch_key_event(
        "keyUp",
        key="Enter",
        code="Enter",
        windows_virtual_key_code=13,
        native_virtual_key_code=13,
    ))


async def _clear_geo_tags(tab) -> int:
    """Entfernt alle bestehenden Ort-Tags (Muelleimer-Icon-Anker klicken).

    Trash-Anker ist <a href="#"><i class="fas fa-trash"></i></a> in der
    location-select-widget Box.
    """
    try:
        removed = await tab.evaluate(
            """(() => {
                let count = 0;
                // Trash-Anker im Ort-Widget finden
                const widget = document.querySelector('.location-select-widget');
                if (!widget) return 0;
                const trashes = Array.from(
                    widget.querySelectorAll('a > i.fa-trash, a > i.fas.fa-trash')
                );
                for (const ico of trashes) {
                    const anchor = ico.closest('a');
                    if (anchor) {
                        try {
                            anchor.click();
                            count += 1;
                        } catch (e) {}
                    }
                }
                return count;
            })()"""
        )
        if isinstance(removed, dict) and "value" in removed:
            removed = removed["value"]
        return int(removed) if removed is not None else 0
    except Exception:
        return 0


async def _set_geo_via_api(tab, geo_query: str, expected_substring: str) -> tuple[bool, Optional[dict]]:
    """Setzt Ort via direkter Location-API + Manipulation des hidden id_location.

    API: GET /de/api/location?q=<query>
    Response-Format:
        {"results": [
            {"value": "zip:45357", "label": "45357 Essen", "category": "PLZ",
             "lat": ..., "lon": ...},
            {"value": 10800, "label": "Essen, Nordrhein-Westfalen",
             "category": "Kreisfreie Stadt", ...}
        ]}

    Hidden Form-Input:
        <input id="id_location" name="location" value='{"type":"id","value":[{
            "location": <value>, "radius": 0, "polygon": null
        }]}'>
    """
    try:
        raw = await tab.evaluate(
            f"""(async () => {{
                try {{
                    const resp = await fetch(
                        '/de/api/location?q=' + encodeURIComponent({json.dumps(geo_query)}),
                        {{credentials: 'include'}}
                    );
                    if (!resp.ok) return JSON.stringify({{error: 'http_' + resp.status}});
                    const txt = await resp.text();
                    return txt;
                }} catch (e) {{
                    return JSON.stringify({{error: e.message || String(e)}});
                }}
            }})()""",
            await_promise=True,
        )
        if isinstance(raw, dict) and "value" in raw:
            raw = raw["value"]
        if not isinstance(raw, str):
            print(f">>>   Location-API: unerwarteter Returntyp {type(raw)}",
                  file=sys.stderr, flush=True)
            return False, None
        try:
            data = json.loads(raw)
        except Exception:
            print(f">>>   Location-API JSON-Parse FAIL: {raw[:200]}",
                  file=sys.stderr, flush=True)
            return False, None
        if isinstance(data, dict) and "error" in data:
            print(f">>>   Location-API ERROR: {data['error']}",
                  file=sys.stderr, flush=True)
            return False, None

        results = data.get("results") if isinstance(data, dict) else None
        if not results or not isinstance(results, list):
            print(">>>   Location-API: keine results",
                  file=sys.stderr, flush=True)
            return False, None

        # Pick: bevorzugt exaktes Substring-Match im label;
        # bei PLZ-Query (rein numerisch) bevorzuge category=PLZ
        expected_lower = expected_substring.lower()
        is_plz_query = geo_query.strip().isdigit()
        picked = None
        if is_plz_query:
            for r in results:
                if r.get("category") == "PLZ":
                    picked = r
                    break
        if not picked:
            for r in results:
                label = str(r.get("label") or "")
                if expected_lower in label.lower():
                    picked = r
                    break
        if not picked:
            picked = results[0]

        picked_value = picked.get("value")
        picked_label = picked.get("label", "")
        picked_cat = picked.get("category", "")
        print(
            f">>>   Location-API: value={picked_value!r} "
            f"label={picked_label!r} cat={picked_cat!r}",
            file=sys.stderr, flush=True,
        )
        if picked_value is None:
            return False, picked

        # Hidden Form-Input mit dem location-Value setzen
        loc_json_value = json.dumps({
            "type": "id",
            "value": [{
                "location": picked_value,
                "radius": 0,
                "polygon": None,
            }],
        }, ensure_ascii=False)
        await tab.evaluate(
            f"""(() => {{
                const inp = document.getElementById('id_location');
                if (!inp) return false;
                inp.value = {json.dumps(loc_json_value)};
                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                return true;
            }})()"""
        )
        return True, {
            "value": picked_value,
            "label": picked_label,
            "category": picked_cat,
        }
    except Exception as e:
        print(f">>>   _set_geo_via_api Exception: {e}",
              file=sys.stderr, flush=True)
        return False, None


def _geo_state_matches(geo_state: Optional[str], expected: str) -> bool:
    """Prueft den Ort-Tag der Ergebnis-Seite gegen die erwartete Geo-Eingabe.

    'Neuer Ort' ist der leere Slot — dann liefert Immometrica bundesweite Zahlen.
    Die wurden am 2026-09-10 als PLZ-Werte gemeldet (status ok, 41284 Angebote,
    3341 EUR/m2 statt 1878), weil niemand den Tag gegengeprueft hat.
    """
    if not geo_state:
        return False
    gs = geo_state.strip()
    if gs == "Neuer Ort":
        return False
    if expected.strip().lower() not in gs.lower():
        return False
    # Stadt-Block: ein haengengebliebener PLZ-Tag ("45355 Essen") enthaelt den
    # Stadtnamen ebenfalls — er darf die Stadt-Config trotzdem nicht bestaetigen.
    if not expected.strip().isdigit() and re.match(r"^\d{5}\b", gs):
        return False
    return True


async def _wait_for_geo_suggestions(tab, timeout_s: float = 12.0) -> int:
    """Pollt auf Optionen im React-Select-Menue. Returns Anzahl Optionen.

    Der Enter-Keystroke waehlt die fokussierte Option — ist das Menue noch leer,
    passiert nichts und der Ort bleibt ungesetzt (Ausfall-Modus 2026-09-10:
    bundesweite Zahlen unter PLZ-Label).
    """
    import time
    deadline = time.monotonic() + timeout_s
    while True:
        n = await tab.evaluate(
            """document.querySelectorAll(
                '[id^="react-select-"][id*="-option"]').length"""
        )
        if isinstance(n, dict) and "value" in n:
            n = n["value"]
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            return n
        if time.monotonic() >= deadline:
            return 0
        await asyncio.sleep(0.4)


async def _enter_geo(tab, geo_query: str, expected_substring: str) -> bool:
    """Tippt geo_query in React-Select Ort-Eingabe + drueckt Enter.

    Wichtig: User-Workflow ist tippen + Enter (echter Keystroke via CDP).
    `send_keys('Enter')` macht KEINEN Enter-Key, sondern 5 char-events
    'E', 'n', 't', 'e', 'r'. Wir muessen `_press_enter` benutzen.

    Vorbedingung: Geo muss VOR Period gesetzt werden — Period-Klick
    bricht React-Select (kein Suggestions-Trigger danach).
    """
    try:
        # 1) Existing Tags loeschen
        cleared = await _clear_geo_tags(tab)
        if cleared:
            print(f">>>   Ort-Tags entfernt: {cleared}",
                  file=sys.stderr, flush=True)
        await asyncio.sleep(2.0)

        # 2) Auf "Neuer Ort"-Slot klicken um React-Select zu fokussieren
        try:
            await tab.evaluate(
                """(() => {
                    const widget = document.querySelector('.location-select-widget');
                    if (!widget) return false;
                    const toggle = widget.querySelector('.location-toggle');
                    if (toggle) toggle.click();
                    return true;
                })()"""
            )
            await asyncio.sleep(2.0)
        except Exception:
            pass

        # 3) React-Select-Input mit Delays zwischen Chars (API-Calls!)
        inp = await tab.query_selector(
            'input[id^="react-select-"][id$="-input"]'
        )
        if not inp:
            print(">>>   ERR: react-select Input nicht gefunden",
                  file=sys.stderr, flush=True)
            return False
        await inp.click()
        await asyncio.sleep(1.0)
        for ch in geo_query:
            await inp.send_keys(ch)
            await asyncio.sleep(0.3)

        # 4) Suggestions laden lassen — Polling statt Blind-Sleep, damit der
        #    Enter-Keystroke nicht auf ein leeres React-Select-Menue trifft.
        options = await _wait_for_geo_suggestions(tab, timeout_s=12.0)
        print(f">>>   Tippe '{geo_query}' -> Vorschlaege: {options}",
              file=sys.stderr, flush=True)
        if not options:
            print(">>>   ERR: keine Ort-Vorschlaege im React-Select-Menue",
                  file=sys.stderr, flush=True)
            return False

        # 5) Enter-Key via CDP (echter Keystroke, React-Select picks first option)
        await _press_enter(tab)

        # 6) Tag-Erscheinen abwarten
        await asyncio.sleep(3.0)

        # 7) Verifikation via Body-Text
        body = await _eval_str(tab, "(document.body && document.body.innerText) || ''")
        geo_now = parse_geo_state(body or "")
        ok = _geo_state_matches(geo_now, expected_substring)
        print(f">>>   Geo-Tag nach Enter: {geo_now!r} -> ok={ok}",
              file=sys.stderr, flush=True)
        return ok
    except Exception as e:
        print(f">>>   _enter_geo Exception: {e}",
              file=sys.stderr, flush=True)
        return False


_RADIO_IDS = {
    "ETW": "id_type_0",
    "Mietwohnung": "id_type_1",
    "Hauskauf": "id_type_2",
    "Hausmiete": "id_type_3",
}


async def _select_radio(tab, label_text: str) -> bool:
    """Klickt Object-Typ-Radio via native Browser-Click auf das Label-Element.

    Bei Bootstrap custom-control ist <input type="radio"> versteckt;
    nur <label for="id_type_X"> ist click-able. Wir nutzen nodriver's
    native click() (echter Mouse-Event), nicht JS-Synth-click.
    """
    radio_id = _RADIO_IDS.get(label_text)
    if not radio_id:
        return False
    try:
        label = await tab.query_selector(f'label[for="{radio_id}"]')
        if not label:
            # Fallback: Element via JS
            await tab.evaluate(
                f"""(() => {{
                    const lbl = document.querySelector('label[for=' + {json.dumps(radio_id)} + ']');
                    if (lbl) lbl.click();
                }})()"""
            )
            return True
        await label.click()
        await asyncio.sleep(0.4)
        return True
    except Exception:
        return False


async def _click_bauliches_tab(tab) -> bool:
    try:
        clicked = await tab.evaluate(
            """(() => {
                const tabs = Array.from(document.querySelectorAll('a, button'))
                    .filter(b => b.innerText.trim() === 'Bauliches');
                if (tabs.length === 0) return false;
                tabs[0].click();
                return true;
            })()"""
        )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        return bool(clicked)
    except Exception:
        return False


async def _click_mfh_checkbox(tab) -> bool:
    """Klickt 'Mehrfamilienhaus' unter 'Art' im Bauliches-Tab."""
    try:
        clicked = await tab.evaluate(
            """(() => {
                const cbs = Array.from(document.querySelectorAll(
                    'input[type="checkbox"]'
                ));
                for (const cb of cbs) {
                    const wrap = cb.parentElement
                        ? cb.parentElement.innerText.trim() : '';
                    if (wrap.includes('Mehrfamilienhaus')) {
                        if (!cb.checked) cb.click();
                        return true;
                    }
                }
                return false;
            })()"""
        )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        return bool(clicked)
    except Exception:
        return False


async def _uncheck_mfh_checkbox(tab) -> bool:
    try:
        clicked = await tab.evaluate(
            """(() => {
                const cbs = Array.from(document.querySelectorAll(
                    'input[type="checkbox"]'
                ));
                for (const cb of cbs) {
                    const wrap = cb.parentElement
                        ? cb.parentElement.innerText.trim() : '';
                    if (wrap.includes('Mehrfamilienhaus')) {
                        if (cb.checked) cb.click();
                        return true;
                    }
                }
                return false;
            })()"""
        )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        return bool(clicked)
    except Exception:
        return False


async def _click_create_stat(tab) -> bool:
    """Triggert das Statistik-Submit via Native-Click auf 'Statistik erstellen'.

    IntercoolerJS reagiert nur auf echte UI-Clicks; reine Form.submit() macht
    Full-Page-Reload, was den State zerstoert.
    """
    try:
        btn = None
        try:
            btn = await tab.find("Statistik erstellen", best_match=True, timeout=3)
        except Exception:
            pass
        if btn:
            await btn.click()
            print(">>>   Native-Click 'Statistik erstellen'",
                  file=sys.stderr, flush=True)
            return True
    except Exception as e:
        print(f">>>   Click 'Statistik erstellen' FAIL: {e}",
              file=sys.stderr, flush=True)

    # Letzter Fallback: JS-Click auf gefundenen Button
    try:
        clicked = await tab.evaluate(
            """(() => {
                const btns = Array.from(document.querySelectorAll('button, a'))
                    .filter(b => b.innerText.trim() === 'Statistik erstellen');
                if (btns.length === 0) return false;
                btns[0].click();
                return true;
            })()"""
        )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        return bool(clicked)
    except Exception:
        return False


async def _wait_for_stat_loaded(tab, timeout_s: float = 90.0) -> bool:
    """Wartet bis 'Wird geladen...' verschwunden ist und ein Übersicht-Block sichtbar ist.

    Default 90s — Immometrica-Server-Response ist variabel und kann
    bei vollem Filter (Geo + Baujahr + Radio + MFH) lang dauern.
    """
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            body = await tab.evaluate(
                "(document.body && document.body.innerText) || ''"
            )
            if isinstance(body, dict) and "value" in body:
                body = body["value"]
            if isinstance(body, str) and "Übersicht:" in body and "Wird geladen" not in body:
                return True
        except Exception:
            pass
        await asyncio.sleep(0.6)
    return False


# Heading-Mapping: Radio-Label -> erwartete Stat-Page-Übersicht.heading.
# Wird in _run_config_in_session zur Verifikation genutzt, dass die Server-Response
# tatsächlich zur aktuellen Filter-Kombination passt (heading-basierter Diff-Check).
# Eingefuehrt v3.3 nach Diagnose-Lauf 2026-05-26, der zeigte, dass _wait_for_stat_loaded
# allein zu früh true wird (alte Stat-Page noch im DOM, neue noch nicht gerendert).
_RADIO_TO_EXPECTED_HEADING = {
    "ETW":         "Wohnung kaufen",
    "Mietwohnung": "Wohnung mieten",
    "Hauskauf":    "Haus kaufen",
}


async def _wait_for_stat_heading(tab, expected_heading: str, timeout_s: float = 30.0) -> tuple[bool, Optional[str]]:
    """Pollt die Übersicht-Heading bis sie zum erwarteten Radio-Label passt.

    Returns:
        (match: bool, actual_heading: Optional[str])
    """
    import time
    deadline = time.monotonic() + timeout_s
    actual = None
    while time.monotonic() < deadline:
        try:
            body = await tab.evaluate(
                "(document.body && document.body.innerText) || ''"
            )
            if isinstance(body, dict) and "value" in body:
                body = body["value"]
            if isinstance(body, str):
                parsed = parse_stat_block(body)
                ueb = parsed.get("uebersicht") or {}
                actual = ueb.get("heading")
                if actual and actual.strip().lower() == expected_heading.strip().lower():
                    return True, actual
        except Exception:
            pass
        await asyncio.sleep(0.6)
    return False, actual


_CHART_DIM_LABEL_PATTERNS = {
    "zimmer": ("Zi.",),
    "wohnflaeche": ("m²",),
    "baujahr": ("vor", "bis", "nach", "Neubau"),
}

_CHART_METRIC_ORDER = ("angebote", "kaufpreis", "online_dauer")


def _classify_chart_dim(labels: list) -> Optional[str]:
    """Erkennt die Dimension eines Charts anhand der X-Achsen-Labels.

    Returns 'zimmer' | 'wohnflaeche' | 'baujahr' | None.
    """
    if not labels:
        return None
    sample = " ".join(str(s) for s in labels)
    if "Zi." in sample:
        return "zimmer"
    if "m²" in sample:
        return "wohnflaeche"
    if "vor 1" in sample or "Neubau" in sample or "nach 2" in sample:
        return "baujahr"
    return None


async def _get_chart_data(tab) -> dict:
    """Extrahiert die Chart.js-Datenpunkte (alle 18 Charts) + strukturiert sie.

    Struktur:
        {
            "uebersicht": {
                "zimmer":      {"angebote": [...], "kaufpreis": [...], "online_dauer": [...], "labels": [...]},
                "wohnflaeche": {...},
                "baujahr":     {...}
            },
            "zusatzinfo": {... gleiche Struktur ...},
            "raw_count": <int>
        }

    Die ersten 9 Charts gehoeren zur Uebersicht, die letzten 9 zur
    Zusatzinfo. Innerhalb jeder Gruppe: 3 Dimensionen × 3 Metriken
    (Angebote → Kaufpreis → Online-Dauer pro Dimension).
    """
    try:
        raw = await tab.evaluate(
            """(() => {
                let instances = [];
                try {
                    if (window.Chart && Chart.instances) {
                        if (Array.isArray(Chart.instances)) {
                            instances = Chart.instances;
                        } else if (typeof Chart.instances.forEach === 'function') {
                            Chart.instances.forEach(c => instances.push(c));
                        } else {
                            instances = Object.values(Chart.instances);
                        }
                    }
                    if (instances.length === 0 && window.Chart
                            && typeof Chart.getChart === 'function') {
                        document.querySelectorAll('canvas').forEach(c => {
                            const inst = Chart.getChart(c);
                            if (inst) instances.push(inst);
                        });
                    }
                } catch (e) {
                    return JSON.stringify({err: 'access', msg: e.message});
                }
                return JSON.stringify(instances.map(c => ({
                    canvas_id: (c.canvas && c.canvas.id) || null,
                    type: c.config ? c.config.type : (c.type || null),
                    labels: (c.data && c.data.labels) || [],
                    data: (((c.data && c.data.datasets) || [])[0] || {}).data || []
                })));
            })()"""
        )
        if isinstance(raw, dict) and "value" in raw:
            raw = raw["value"]
        if not isinstance(raw, str):
            return {"raw_count": 0, "uebersicht": None, "zusatzinfo": None,
                    "error": f"unexpected return type {type(raw).__name__}"}
        try:
            charts = json.loads(raw)
        except Exception as e:
            return {"raw_count": 0, "uebersicht": None, "zusatzinfo": None,
                    "error": f"json parse: {e}"}
        if isinstance(charts, dict) and "err" in charts:
            return {"raw_count": 0, "uebersicht": None, "zusatzinfo": None,
                    "error": f"js: {charts.get('msg')}"}

        n = len(charts)
        if n < 9:
            return {"raw_count": n, "uebersicht": None, "zusatzinfo": None,
                    "error": f"only {n} charts found (expected 9 or 18)"}

        def _bucket_group(chart_slice):
            """Strukturiert 9 Charts → {zimmer/wohnflaeche/baujahr: {angebote/kaufpreis/online_dauer, labels}}."""
            out = {}
            # Gruppiere nach Dimension
            by_dim: dict = {}
            for ch in chart_slice:
                dim = _classify_chart_dim(ch.get("labels") or [])
                if not dim:
                    continue
                by_dim.setdefault(dim, []).append(ch)
            for dim, charts_in_dim in by_dim.items():
                # Metrik-Reihenfolge: angebote, kaufpreis, online_dauer
                block = {"labels": list(charts_in_dim[0].get("labels") or [])}
                for i, metric in enumerate(_CHART_METRIC_ORDER):
                    if i < len(charts_in_dim):
                        block[metric] = list(charts_in_dim[i].get("data") or [])
                    else:
                        block[metric] = None
                out[dim] = block
            return out

        # 9 Charts → nur Uebersicht
        # 18 Charts → 9 Uebersicht + 9 Zusatzinfo
        if n >= 18:
            uebersicht = _bucket_group(charts[:9])
            zusatzinfo = _bucket_group(charts[9:18])
        else:
            uebersicht = _bucket_group(charts[:9])
            zusatzinfo = None

        return {
            "raw_count": n,
            "uebersicht": uebersicht,
            "zusatzinfo": zusatzinfo,
        }
    except Exception as e:
        return {"raw_count": 0, "uebersicht": None, "zusatzinfo": None,
                "error": str(e)}


async def _get_dom_body(tab) -> str:
    try:
        body = await tab.evaluate(
            "(document.body && document.body.innerText) || ''"
        )
        if isinstance(body, dict) and "value" in body:
            body = body["value"]
        return body or ""
    except Exception:
        return ""


async def _save_screenshot(tab, label: str, ts: str) -> Optional[Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{ts}_immometrica_{label}.png"
    try:
        await tab.save_screenshot(filename=str(p), full_page=False)
        return p
    except Exception:
        return None


async def _verify_radio_checked(tab, radio_id: str) -> bool:
    try:
        r = await tab.evaluate(
            f"""(() => {{
                const r = document.getElementById({json.dumps(radio_id)});
                return r ? !!r.checked : false;
            }})()"""
        )
        if isinstance(r, dict) and "value" in r:
            r = r["value"]
        return bool(r)
    except Exception:
        return False


async def _verify_mfh_checked(tab) -> bool:
    try:
        r = await tab.evaluate(
            """(() => {
                const cbs = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                for (const cb of cbs) {
                    const wrap = cb.parentElement ? cb.parentElement.innerText.trim() : '';
                    if (wrap.includes('Mehrfamilienhaus')) return !!cb.checked;
                }
                return false;
            })()"""
        )
        if isinstance(r, dict) and "value" in r:
            r = r["value"]
        return bool(r)
    except Exception:
        return False


async def _verify_geo_set(tab, expected_substring: str) -> Optional[str]:
    try:
        body = await _get_dom_body(tab)
        geo = parse_geo_state(body)
        if geo and expected_substring.lower() in geo.lower() and geo != "Neuer Ort":
            return geo
        return None
    except Exception:
        return None


async def _wait_for_radio(tab, radio_id: str, timeout_s: float = 6.0) -> bool:
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if await _verify_radio_checked(tab, radio_id):
            return True
        await asyncio.sleep(0.4)
    return False


async def _wait_for_mfh(tab, want_checked: bool, timeout_s: float = 6.0) -> bool:
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        cur = await _verify_mfh_checked(tab)
        if cur == want_checked:
            return True
        await asyncio.sleep(0.4)
    return False


async def _wait_for_geo(tab, expected_substring: str, timeout_s: float = 6.0) -> Optional[str]:
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        geo = await _verify_geo_set(tab, expected_substring)
        if geo:
            return geo
        await asyncio.sleep(0.4)
    return None


async def _run_config_in_session(
    tab,
    *,
    radio: str,
    mfh: bool,
    baujahr_von: int,
    baujahr_bis: int,
    label: str,
    ts: str,
    geo_expected: Optional[str] = None,
) -> dict:
    """Setzt Radio + MFH + Baujahr-Range + Submit + parse — OHNE Page-Reload.

    Vorbedingung: Geo + Period sind bereits gesetzt. Diese Funktion wechselt
    nur die Filter, die zwischen Configs variieren (Radio, MFH, Baujahr).
    """
    radio_id = _RADIO_IDS[radio]

    # Radio + Verifikation + Retry
    await _select_radio(tab, radio)
    radio_ok = await _wait_for_radio(tab, radio_id, timeout_s=6.0)
    if not radio_ok:
        await _select_radio(tab, radio)
        radio_ok = await _wait_for_radio(tab, radio_id, timeout_s=4.0)
    print(f">>>   Radio {radio!r} checked: {radio_ok}",
          file=sys.stderr, flush=True)
    await asyncio.sleep(1.5)

    # Bauliches-Tab oeffnen
    await _click_bauliches_tab(tab)
    await asyncio.sleep(2.0)

    # Baujahr-Range setzen (von, bis)
    baujahr_ok = await _set_baujahr_range(tab, baujahr_von, baujahr_bis)
    await asyncio.sleep(1.0)

    # MFH-Checkbox + Retry (an bei Hauskauf, aus sonst)
    if mfh:
        await _click_mfh_checkbox(tab)
    else:
        await _uncheck_mfh_checkbox(tab)
    mfh_ok = await _wait_for_mfh(tab, mfh, timeout_s=6.0)
    if not mfh_ok:
        if mfh:
            await _click_mfh_checkbox(tab)
        else:
            await _uncheck_mfh_checkbox(tab)
        mfh_ok = await _wait_for_mfh(tab, mfh, timeout_s=4.0)
    print(f">>>   MFH-Checkbox = {mfh}: {mfh_ok}",
          file=sys.stderr, flush=True)
    await asyncio.sleep(1.5)

    # Statistik erstellen
    submitted = await _click_create_stat(tab)
    if not submitted:
        return {
            "status": "error",
            "error": "submit_button_not_found",
            "uebersicht": None,
            "zusatzinfo": None,
        }

    # Stat-Block laden (Body-Sanity: "Übersicht:" da, "Wird geladen" weg, 90s Timeout)
    loaded = await _wait_for_stat_loaded(tab, timeout_s=90.0)
    await asyncio.sleep(2.0)

    # Heading-Diff-Check (v3.3): _wait_for_stat_loaded allein wurde zu früh true,
    # weil das alte Übersicht-DOM beim Submit nicht weggeworfen wird. Wir warten
    # nun explizit darauf, dass die Übersicht-Heading zur aktuellen Radio-Wahl passt.
    expected_heading = _RADIO_TO_EXPECTED_HEADING.get(radio, radio)
    heading_match, heading_actual = await _wait_for_stat_heading(
        tab, expected_heading, timeout_s=30.0
    )

    # Retry-Pass bei Heading-Mismatch (Geo-Wechsel-Race-Condition, eingefuehrt v3.3):
    # Nach Geo-Wechsel von PLZ -> Stadt-Name bleibt das alte Heading der letzten
    # plz_*-Submission im DOM hängen — Submit wird "verschluckt". Ein zweiter Submit
    # nach kurzer Wartezeit triggert die echte Server-Response.
    if not heading_match:
        print(
            f">>>   Heading-Mismatch (actual={heading_actual!r}), Submit-Retry nach 5s...",
            file=sys.stderr, flush=True,
        )
        await asyncio.sleep(5.0)
        await _click_create_stat(tab)
        await _wait_for_stat_loaded(tab, timeout_s=90.0)
        await asyncio.sleep(2.0)
        heading_match, heading_actual = await _wait_for_stat_heading(
            tab, expected_heading, timeout_s=30.0
        )
    print(
        f">>>   Heading-Check: expected={expected_heading!r} actual={heading_actual!r} match={heading_match}",
        file=sys.stderr, flush=True,
    )

    body = await _get_dom_body(tab)
    geo_state_final = parse_geo_state(body)
    parsed = parse_stat_block(body)

    # Chart.js-Datenpunkte ziehen (9 oder 18 Charts)
    charts = await _get_chart_data(tab)

    shot = await _save_screenshot(tab, f"{label}", ts)

    geo_ok = (
        True if geo_expected is None
        else _geo_state_matches(geo_state_final, geo_expected)
    )
    if not geo_ok:
        print(
            f">>>   Geo-Mismatch: erwartet {geo_expected!r}, "
            f"Ort-Tag auf der Ergebnis-Seite {geo_state_final!r}",
            file=sys.stderr, flush=True,
        )

    # Status-Logik:
    # - "geo_mismatch": der Ort-Filter stand nicht (oder auf dem falschen Ort).
    #   Immometrica liefert dann bundesweite Zahlen — die duerfen NIE als
    #   PLZ-/Stadt-Wert durchgehen (Ausfall 2026-09-10).
    # - "stale_heading": Stat-Page wurde nicht aktualisiert (heading hängt fest).
    #   Werte sind die der vorherigen Config — wir setzen uebersicht/zusatzinfo
    #   explizit None, damit Konsumenten (Modul 1) keine falschen Werte lesen.
    #   Was tatsächlich auf der Page stand, bleibt in heading_check.actual zur Diagnose.
    # - "ok": loaded + heading_match + parsed.uebersicht vorhanden
    # - "partial": loaded but missing uebersicht
    # - "error": gar nicht geladen
    if not geo_ok:
        status = "geo_mismatch"
        uebersicht_out = None
        zusatzinfo_out = None
        charts_out: dict = {}
    elif loaded and not heading_match:
        status = "stale_heading"
        uebersicht_out = None
        zusatzinfo_out = None
        charts_out = {}
    elif loaded and parsed.get("uebersicht"):
        status = "ok"
        uebersicht_out = parsed.get("uebersicht")
        zusatzinfo_out = parsed.get("zusatzinfo")
        charts_out = charts
    elif loaded:
        status = "partial"
        uebersicht_out = parsed.get("uebersicht")
        zusatzinfo_out = parsed.get("zusatzinfo")
        charts_out = charts
    else:
        status = "error"
        uebersicht_out = None
        zusatzinfo_out = None
        charts_out = {}

    return {
        "status": status,
        "geo_state": geo_state_final,
        "geo_check": {
            "expected": geo_expected,
            "actual": geo_state_final,
            "match": geo_ok,
        },
        "radio_checked": radio_ok,
        "mfh_checked": mfh_ok,
        "baujahr_set": baujahr_ok,
        "baujahr_von": baujahr_von,
        "baujahr_bis": baujahr_bis,
        "heading_check": {
            "expected": expected_heading,
            "actual": heading_actual,
            "match": heading_match,
        },
        "uebersicht": uebersicht_out,
        "zusatzinfo": zusatzinfo_out,
        "charts": charts_out,
        "screenshot": str(shot) if shot else None,
    }


async def _run_async(
    plz: str,
    stadt: str,
    baujahr: int,
    year_half: str,
    headless: bool,
) -> dict:
    import nodriver as uc

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = _ts_slug()

    print(f">>> Immometrica-Adapter Start ({_ts_iso()})", file=sys.stderr, flush=True)

    browser = await uc.start(
        user_data_dir=str(USER_DATA_DIR),
        headless=headless,
        lang="de-DE",
        browser_args=[
            "--lang=de-DE",
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
    )

    baujahr_bis = _calc_baujahr_bis(baujahr)
    baujahr_von = 1900

    SLOTS = ("plz_etw", "plz_mietwohnung", "plz_mfh",
             "stadt_etw", "stadt_mietwohnung", "stadt_mfh")

    out = {
        "status": "error",
        "portal": "immometrica",
        "marktwert_eur_mittel": None,
        "marktwert_eur_min": None,
        "marktwert_eur_max": None,
        "trends": {"jahre_3": None, "jahr_1": None, "prognose": None},
        "trend_ampel": None,
        "trend_label": None,
        "url": URL_STATISTICS,
        "timestamp": _ts_iso(),
        "screenshot_path": None,
        "extra": {
            "year_half": year_half,
            "plz_input": plz,
            "stadt_input": stadt,
            "baujahr_input": baujahr,
            "baujahr_von": baujahr_von,
            "baujahr_bis": baujahr_bis,
            **{slot: None for slot in SLOTS},
        },
    }

    try:
        # Architektur Phase 2 (siehe Memory [[immometrica-marktstatistik-workflow]]):
        # 1. Dashboard laden (/de/home)
        # 2. Login-Check, ggf. Auto-Login
        # 3. Sidebar-Klick auf "Marktstatistik" (NICHT direkte URL!)
        # 4. Geo (PLZ) setzen via UI - VOR Period
        # 5. Period
        # 6. 3 Configs durchlaufen (ETW, Mietwohnung, Hauskauf)
        # 7. Geo wechseln (Stadt)
        # 8. 3 weitere Configs

        # 1. Dashboard
        tab = await browser.get(URL_HOME)
        await asyncio.sleep(8.0)

        # 2. Login-Check (URL + App-Navigation, siehe _login_state)
        url0, logged_in0 = await _login_state(tab)
        print(f">>> Login-Check: url={url0!r} logged_in={logged_in0}",
              file=sys.stderr, flush=True)

        if not logged_in0:
            print(">>> Session weg, starte Auto-Login",
                  file=sys.stderr, flush=True)
            user, pw = _load_env_creds()
            if not user or not pw:
                out["status"] = "error"
                out["error_code"] = "login_failed"
                out["error_message"] = ".env Credentials fehlen"
                return out
            logged = await _do_login(tab, user, pw)
            if not logged:
                out["status"] = "error"
                out["error_code"] = "login_failed"
                out["error_message"] = "Auto-Login fehlgeschlagen"
                return out
            # Nach Login: zurueck zur Dashboard
            await tab.get(URL_HOME)
            await asyncio.sleep(8.0)

        # 3. Sidebar-Klick auf "Marktstatistik"
        print(">>> Klick auf Sidebar-Link 'Marktstatistik'",
              file=sys.stderr, flush=True)
        clicked = await _click_marktstatistik_sidebar(tab)
        if not clicked:
            print(">>> WARN: Marktstatistik-Sidebar-Link nicht gefunden, "
                  "Fallback auf direkte URL",
                  file=sys.stderr, flush=True)
            await tab.get(URL_STATISTICS)
        # Marktstatistik-Form wird asynchron via IntercoolerJS nachgeladen,
        # 8s reichen nicht. Polling-Wait auf Statistik-Form-Elemente.
        await asyncio.sleep(5.0)
        form_ready = await _wait_for_marktstatistik_ready(tab, timeout_s=20.0)

        # Ohne Formular gibt es keinen Submit-Button — dann meldete der Adapter
        # sechsmal `submit_button_not_found` und verschleierte die echte Ursache
        # (Ausfall 2026-09-10: Session weg, Login stumm fehlgeschlagen).
        # Hier einmal ehrlich abbrechen statt sechs Configs blind durchzuklicken.
        if not form_ready:
            url_now, logged_in_now = await _login_state(tab)
            out["status"] = "error"
            out["error_code"] = (
                "session_lost" if not logged_in_now else "statistics_form_not_ready"
            )
            out["error_message"] = (
                f"Marktstatistik-Formular nicht geladen "
                f"(url={url_now}, logged_in={logged_in_now})"
            )
            print(f">>> ABBRUCH: {out['error_code']} — {out['error_message']}",
                  file=sys.stderr, flush=True)
            return out

        # 6 Configs gruppiert nach Geo: PLZ-Block, dann Stadt-Block
        configs = [
            ("plz_etw",         plz,   plz,   "ETW",         False),
            ("plz_mietwohnung", plz,   plz,   "Mietwohnung", False),
            ("plz_mfh",         plz,   plz,   "Hauskauf",    True),
            ("stadt_etw",       stadt, stadt, "ETW",         False),
            ("stadt_mietwohnung", stadt, stadt, "Mietwohnung", False),
            ("stadt_mfh",       stadt, stadt, "Hauskauf",    True),
        ]

        last_geo: Optional[str] = None
        geo_block_ok = False
        period_set = False
        for slot, geo_q, geo_exp, radio, mfh in configs:
            print(f">>> Config {slot}: geo={geo_q!r} radio={radio} mfh={mfh}",
                  file=sys.stderr, flush=True)

            # Geo nur setzen wenn anders als beim vorherigen Config
            if last_geo != geo_q:
                print(f">>>   Geo setzen: {geo_q}",
                      file=sys.stderr, flush=True)
                geo_block_ok = await _enter_geo(tab, geo_q, geo_exp)
                if not geo_block_ok:
                    print(">>>   Geo retry...",
                          file=sys.stderr, flush=True)
                    geo_block_ok = await _enter_geo(tab, geo_q, geo_exp)
                last_geo = geo_q
                # Nach Geo-Wechsel: Period erneut setzen (sicher)
                period_set = False

            # Ohne gesetzten Ort liefert Immometrica bundesweite Zahlen. Diesen
            # Geo-Block gar nicht erst submitten, statt falsche Werte zu melden.
            if not geo_block_ok:
                print(f">>>   -> uebersprungen: Ort {geo_q!r} nicht gesetzt",
                      file=sys.stderr, flush=True)
                out["extra"][slot] = {
                    "status": "error",
                    "error": "geo_not_set",
                    "geo_check": {"expected": geo_exp, "actual": None,
                                  "match": False},
                    "uebersicht": None,
                    "zusatzinfo": None,
                }
                continue

            if not period_set:
                period_clicked = await _select_period(tab, year_half)
                print(f">>>   Period: {period_clicked}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(2.0)
                period_set = True

            result = await _run_config_in_session(
                tab,
                radio=radio,
                mfh=mfh,
                baujahr_von=baujahr_von,
                baujahr_bis=baujahr_bis,
                label=slot,
                ts=ts,
                geo_expected=geo_exp,
            )
            out["extra"][slot] = result
            print(f">>>   -> status={result.get('status')} geo_state={result.get('geo_state')!r}",
                  file=sys.stderr, flush=True)
            uebersicht = result.get("uebersicht") if isinstance(result, dict) else None
            if uebersicht:
                print(
                    f">>>   -> Anz={uebersicht.get('anzahl_angebote')} "
                    f"Preis/m²={uebersicht.get('median_preis_eur_per_qm')} "
                    f"Rendite={uebersicht.get('rendite_pct')}",
                    file=sys.stderr, flush=True,
                )

        # Status final
        non_error = sum(
            1 for slot in SLOTS
            if isinstance(out["extra"].get(slot), dict)
            and out["extra"][slot].get("status") in ("ok", "partial")
            and out["extra"][slot].get("uebersicht")
        )
        total = len(SLOTS)
        if non_error == total:
            out["status"] = "ok"
        elif non_error > 0:
            out["status"] = "partial"
            out["error_code"] = "partial_configs"
            out["error_message"] = f"{total - non_error} von {total} Configs unvollstaendig"
        else:
            out["status"] = "error"
            out["error_code"] = "all_configs_failed"
            out["error_message"] = "Keine Config lieferte Werte"

        return out

    except Exception as e:
        print(f">>> Exception: {e}\n{traceback.format_exc()}",
              file=sys.stderr, flush=True)
        out["status"] = "error"
        out["error_code"] = "exception"
        out["error_message"] = str(e)
        return out
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def run_immometrica(
    plz: str,
    stadt: str,
    baujahr: int,
    year_half: str = "latest",
    headless: bool = True,
) -> dict:
    """Sync-Wrapper. Liefert das JSON-Schema (RunResult-kompatibel) als dict."""
    import nodriver as uc
    return uc.loop().run_until_complete(
        _run_async(plz, stadt, baujahr, year_half, headless)
    )


class ImmometricaPortal:
    """Adapter-Klasse fuer PORTAL_REGISTRY (kompatibel zu PortalBase-Idiom).

    Aber: Erbt NICHT von PortalBase, weil Immometrica-Adapter nodriver statt
    Playwright nutzt (reCAPTCHA). Stattdessen exponiert es eine
    run(datensatz, cfg)-Methode, die PORTAL_REGISTRY direkt callen kann.
    """

    NAME = "immometrica"
    START_URL = URL_STATISTICS

    def run(self, datensatz, cfg=None) -> dict:
        # datensatz ist GeneralisierterDatensatz oder hat .plz / .ort / .baujahr
        plz = getattr(datensatz, "plz", None) or ""
        stadt = getattr(datensatz, "ort", None) or ""
        baujahr = getattr(datensatz, "baujahr", None)
        if not plz or not stadt:
            return {
                "status": "error",
                "portal": "immometrica",
                "error_code": "missing_geo",
                "error_message": "PLZ oder Stadt fehlen im Datensatz",
                "timestamp": _ts_iso(),
            }
        if not baujahr:
            return {
                "status": "error",
                "portal": "immometrica",
                "error_code": "missing_baujahr",
                "error_message": "Baujahr fehlt im Datensatz (Pflicht fuer Filter-Range)",
                "timestamp": _ts_iso(),
            }
        headless = bool(getattr(cfg, "headless", True)) if cfg else True
        year_half = (
            getattr(cfg, "year_half", None) if cfg else None
        ) or "H1/2026"
        return run_immometrica(
            plz=plz, stadt=stadt, baujahr=int(baujahr),
            year_half=year_half, headless=headless,
        )
