"""Probe-Skript: Immometrica.com — Login + Suche fuer Prosperstr. 59.

Strategie: Login per Form, dann Adress-Suche, Network-Sniffer protokolliert
alle JSON-Responses. Ziel: API-Endpoint identifizieren, der Marktwert /
Miete / Rendite liefert.

Credentials aus tools/portal-bewertung/.env (IMMOMETRICA_USERNAME +
IMMOMETRICA_PASSWORD).

Lauf:
    .venv\\Scripts\\python.exe inspectors/probe_immometrica.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
RUNS_DIR = PROJ_ROOT / "runs"
BERLIN_TZ = timezone(timedelta(hours=2))

URL_HOME = "https://www.immometrica.com/de"
URL_SEARCH = "https://www.immometrica.com/de/search"
URL_LOGIN_CANDIDATES = [
    "https://www.immometrica.com/de/login",
    "https://www.immometrica.com/de/anmelden",
    "https://www.immometrica.com/de/account/login",
]


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _shoot(page, slug: str) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{_ts()}_immometrica_probe_{slug}.png"
    try:
        page.screenshot(path=str(p), full_page=True)
        print(f">>> Screenshot: {p.name}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>> Screenshot FAIL: {e}", file=sys.stderr, flush=True)


def _dump_dom(page, slug: str) -> None:
    try:
        dom = page.evaluate(
            """() => ({
                url: location.href,
                title: document.title,
                headings: Array.from(document.querySelectorAll('h1,h2,h3'))
                    .map(h => (h.innerText || '').trim()).filter(Boolean).slice(0, 20),
                inputs: Array.from(document.querySelectorAll('input,textarea')).map(e => ({
                    tag: e.tagName,
                    type: e.type, name: e.name, id: e.id,
                    placeholder: e.placeholder || null,
                    ariaLabel: e.getAttribute('aria-label'),
                    dataTestid: e.getAttribute('data-testid'),
                    visible: e.offsetParent !== null,
                })),
                buttons: Array.from(document.querySelectorAll('button, a[href*=login], a[href*=anmelden]')).map(e => ({
                    tag: e.tagName,
                    text: (e.innerText || '').trim().slice(0, 60),
                    href: e.getAttribute('href') || null,
                    type: e.type || null,
                    dataTestid: e.getAttribute('data-testid'),
                    visible: e.offsetParent !== null,
                })).filter(b => b.text || b.dataTestid || b.href),
            })"""
        )
        p = RUNS_DIR / f"{_ts()}_immometrica_probe_{slug}.json"
        p.write_text(json.dumps(dom, indent=2, ensure_ascii=False), encoding="utf-8")
        print(
            f">>> DOM-Dump: {p.name} "
            f"(h={len(dom.get('headings',[]))}, in={len(dom['inputs'])}, "
            f"btn={len(dom['buttons'])})",
            file=sys.stderr, flush=True,
        )
    except Exception as e:
        print(f">>> DOM-Dump FAIL: {e}", file=sys.stderr, flush=True)


def _load_env() -> dict[str, str]:
    env_path = PROJ_ROOT / ".env"
    out: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strasse", default="Prosperstraße")
    parser.add_argument("--hausnr", default="59")
    parser.add_argument("--plz", default="45357")
    parser.add_argument("--ort", default="Essen")
    parser.add_argument("--keep-open", type=int, default=900)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)

    env = _load_env()
    user = env.get("IMMOMETRICA_USERNAME") or os.environ.get("IMMOMETRICA_USERNAME", "")
    pw = env.get("IMMOMETRICA_PASSWORD") or os.environ.get("IMMOMETRICA_PASSWORD", "")
    if not user or not pw:
        print(">>> ERROR: IMMOMETRICA_USERNAME / IMMOMETRICA_PASSWORD fehlen in .env",
              file=sys.stderr, flush=True)
        return 1

    from playwright.sync_api import sync_playwright

    print(f">>> Oeffne {URL_HOME} (headed)", file=sys.stderr, flush=True)
    network_log: list[dict] = []

    with sync_playwright() as pw_runtime:
        browser = pw_runtime.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 1000},
        )
        page = ctx.new_page()

        # Network-Sniffer
        def _on_response(resp) -> None:
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if "immometrica" not in url:
                return
            if not ("json" in ct.lower() or "/api/" in url or "search" in url):
                return
            entry = {
                "status": resp.status,
                "url": url[:300],
                "content_type": ct[:80],
            }
            try:
                if "json" in ct.lower() and resp.status < 400:
                    body = resp.text()
                    entry["body_snippet"] = body[:3000]
            except Exception:
                pass
            network_log.append(entry)

        page.on("response", _on_response)

        page.goto(URL_HOME, wait_until="domcontentloaded")
        page.wait_for_timeout(2_500)
        _shoot(page, "10_home")
        _dump_dom(page, "10_home_dom")

        # Cookie banner: usercentrics-style kill (vorsichtshalber)
        try:
            page.evaluate(
                """() => document.querySelectorAll(
                    '#usercentrics-root, [id*="usercentrics"]'
                ).forEach(el => el.remove())"""
            )
        except Exception:
            pass

        # ---- Schritt: Login-Page suchen ----
        print(">>> Step Login: navigiere zur Login-Page", file=sys.stderr, flush=True)
        login_url = None
        for url in URL_LOGIN_CANDIDATES:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                if resp and resp.status < 400:
                    login_url = url
                    print(f">>>   Login-URL: {url} (status {resp.status})",
                          file=sys.stderr, flush=True)
                    break
            except Exception:
                continue
        if not login_url:
            print(">>>   Keine Login-URL gefunden, schaue nach Link/Button auf Home",
                  file=sys.stderr, flush=True)
            page.goto(URL_HOME, wait_until="domcontentloaded")
            page.wait_for_timeout(1_000)
            for sel in [
                'a[href*="login"]', 'a[href*="anmelden"]',
                'button:has-text("Login")', 'button:has-text("Anmelden")',
                'a:has-text("Login")', 'a:has-text("Anmelden")',
            ]:
                try:
                    loc = page.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        loc.click(timeout=3_000)
                        print(f">>>   Login-Link geklickt: {sel}",
                              file=sys.stderr, flush=True)
                        break
                except Exception:
                    continue

        page.wait_for_timeout(2_000)
        _shoot(page, "20_login_page")
        _dump_dom(page, "20_login_page_dom")

        # ---- Login: User + Passwort ----
        print(">>> Step Login: Credentials eingeben", file=sys.stderr, flush=True)
        # Username
        user_filled = False
        for sel in [
            'input[name="email"]', 'input[type="email"]',
            'input[name="username"]', 'input[id*="email"]', 'input[id*="user"]',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.fill(user, timeout=4_000)
                    user_filled = True
                    print(f">>>   Username via {sel}", file=sys.stderr, flush=True)
                    break
            except Exception:
                continue
        # Passwort
        pw_filled = False
        for sel in [
            'input[type="password"]', 'input[name="password"]',
            'input[id*="password"]',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.fill(pw, timeout=4_000)
                    pw_filled = True
                    print(f">>>   Passwort via {sel}", file=sys.stderr, flush=True)
                    break
            except Exception:
                continue

        if not user_filled or not pw_filled:
            print(">>>   ABBRUCH: Login-Felder nicht gefunden",
                  file=sys.stderr, flush=True)
            _shoot(page, "21_login_fields_missing")

        # Submit
        for sel in [
            'button[type="submit"]',
            'button:has-text("Anmelden")',
            'button:has-text("Login")',
            'button:has-text("Einloggen")',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=4_000)
                    print(f">>>   Submit via {sel}", file=sys.stderr, flush=True)
                    break
            except Exception:
                continue
        page.wait_for_timeout(4_000)
        _shoot(page, "30_after_login")
        _dump_dom(page, "30_after_login_dom")

        # ---- Suche-Page ----
        print(">>> Step Search: gehe zu /de/search", file=sys.stderr, flush=True)
        try:
            page.goto(URL_SEARCH, wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(2_500)
        except Exception as e:
            print(f">>>   Goto search FAIL: {e}", file=sys.stderr, flush=True)
        _shoot(page, "40_search_page")
        _dump_dom(page, "40_search_page_dom")

        # ---- Adress-Suche ----
        # Mehrere Strategien fuer Adress-Input
        print(">>> Step Search: Adresse eingeben", file=sys.stderr, flush=True)
        adress_str = f"{args.strasse} {args.hausnr}, {args.plz} {args.ort}"
        filled = False
        for sel in [
            'input[placeholder*="Adresse"]',
            'input[placeholder*="Straße"]',
            'input[placeholder*="Ort"]',
            'input[name*="search"]',
            'input[name*="address"]',
            'input[type="search"]',
            'input[type="text"]',
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.fill(adress_str, timeout=4_000)
                    filled = True
                    print(f">>>   Adresse {adress_str!r} via {sel}",
                          file=sys.stderr, flush=True)
                    break
            except Exception:
                continue
        if not filled:
            print(">>>   Adress-Feld NICHT GEFUNDEN", file=sys.stderr, flush=True)

        page.wait_for_timeout(2_000)
        _shoot(page, "50_address_typed")
        _dump_dom(page, "50_address_typed_dom")

        # Versuch: ArrowDown + Enter (Autocomplete)
        try:
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(400)
            page.keyboard.press("Enter")
        except Exception:
            pass
        page.wait_for_timeout(5_000)
        _shoot(page, "60_after_search")
        _dump_dom(page, "60_after_search_dom")

        # Network-Log dumpen
        try:
            net_path = RUNS_DIR / f"{_ts()}_immometrica_probe_network.json"
            net_path.write_text(
                json.dumps(network_log, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(
                f">>> Network-Log: {net_path.name} "
                f"({len(network_log)} Eintraege)",
                file=sys.stderr, flush=True,
            )
        except Exception as e:
            print(f">>> Network-Log FAIL: {e}", file=sys.stderr, flush=True)

        print(
            f">>> Browser bleibt {args.keep_open}s offen. "
            "Schliesse Fenster zum Beenden.",
            file=sys.stderr, flush=True,
        )
        end = time.monotonic() + args.keep_open
        try:
            while not page.is_closed() and time.monotonic() < end:
                time.sleep(2)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
