"""Autonomer Login-Versuch fuer Immometrica via nodriver.

nodriver ist der modernste Anti-Detection-Chrome-Treiber (Successor zu
undetected-chromedriver). Steuert Chrome direkt via CDP, aber patcht
alle bekannten Bot-Marker. Hoechste Erfolgsquote gegen reCAPTCHA, falls
ueberhaupt eine Browser-Automation durchgehen kann.

Pflichten dieses Skripts:
1. Cookie-Banner + Newsletter-Modal dismissen
2. 'Einloggen'-Button klicken
3. E-Mail + Passwort tippen (mit Random-Delays = menschlich)
4. reCAPTCHA-Checkbox klicken (passive Bypass falls Score okay)
5. Auf Login-Erfolg warten (Dashboard-URL oder spezifische Heuristik)
6. Cookies + Storage-State exportieren fuer Adapter-Nutzung

Lauf:
    .venv\\Scripts\\python.exe inspectors/login_immometrica_autonomous.py
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
RUNS_DIR = PROJ_ROOT / "runs"
STATE_DIR = PROJ_ROOT / "learned_selectors"
USER_DATA_DIR = STATE_DIR / "immometrica_nodriver_userdata"
COOKIES_OUT = STATE_DIR / "immometrica_cookies.json"
BERLIN_TZ = timezone(timedelta(hours=2))

URL_HOME = "https://www.immometrica.com/de"


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


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


async def _human_type(elem, text: str) -> None:
    """Tippt Text mit Random-Delays (menschlicher)."""
    for char in text:
        await elem.send_keys(char)
        await asyncio.sleep(random.uniform(0.04, 0.18))


async def _save_shot(tab, slug: str) -> Path | None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    p = RUNS_DIR / f"{_ts()}_immometrica_nodriver_{slug}.png"
    try:
        await tab.save_screenshot(filename=str(p), full_page=False)
        print(f">>> Screenshot: {p.name}", file=sys.stderr, flush=True)
        return p
    except Exception as e:
        print(f">>> Screenshot FAIL ({slug}): {e}",
              file=sys.stderr, flush=True)
        return None


async def _dismiss_cookies(tab) -> bool:
    """Versucht Cookie-Banner zu schliessen."""
    candidates = [
        "Alle akzeptieren", "Akzeptieren", "Zustimmen",
        "Einverstanden", "Verstanden", "OK", "Schließen",
        "geht klar", "Geht klar",
    ]
    for txt in candidates:
        try:
            elem = await tab.find(text=txt, best_match=True, timeout=2)
            if elem:
                await elem.click()
                print(f">>>   Cookies via {txt!r}", file=sys.stderr, flush=True)
                await asyncio.sleep(1.0)
                return True
        except Exception:
            continue
    return False


async def _dismiss_newsletter(tab) -> bool:
    """Versucht Newsletter/Workshop-Modal zu schliessen."""
    # Versuch 1: ESC-Taste
    try:
        await tab.evaluate("document.activeElement && document.activeElement.blur()")
        await tab.send_keys("Escape")
        await asyncio.sleep(0.5)
    except Exception:
        pass
    # Versuch 2: Klick auf X-Buttons
    for sel in [
        '[aria-label="Close"]',
        '[aria-label="Schließen"]',
        'button.close',
        '.modal-close',
        '[class*="close-button"]',
    ]:
        try:
            elem = await tab.query_selector(sel)
            if elem:
                await elem.click()
                print(f">>>   Newsletter-Close via {sel}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(0.5)
                return True
        except Exception:
            continue
    return False


async def _click_login_button(tab) -> bool:
    """Klickt den 'Einloggen'-Header-Button."""
    for text in ["Einloggen", "Login", "Anmelden"]:
        try:
            elem = await tab.find(text=text, best_match=True, timeout=3)
            if elem:
                await elem.click()
                print(f">>>   Login-Button via {text!r}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(2.5)
                return True
        except Exception:
            continue
    return False


async def _fill_login_form(tab, email: str, password: str) -> tuple[bool, bool]:
    """Fuellt E-Mail + Passwort. Returns (email_filled, password_filled)."""
    email_filled = False
    pw_filled = False

    for sel in [
        'input[type="email"]',
        'input[name="email"]',
        'input[name="username"]',
        'input[id*="email"]',
    ]:
        try:
            elem = await tab.query_selector(sel)
            if elem:
                await elem.click()
                await asyncio.sleep(0.3)
                await _human_type(elem, email)
                email_filled = True
                print(f">>>   E-Mail via {sel}", file=sys.stderr, flush=True)
                break
        except Exception:
            continue

    for sel in [
        'input[type="password"]',
        'input[name="password"]',
    ]:
        try:
            elem = await tab.query_selector(sel)
            if elem:
                await elem.click()
                await asyncio.sleep(0.3)
                await _human_type(elem, password)
                pw_filled = True
                print(f">>>   Passwort via {sel}", file=sys.stderr, flush=True)
                break
        except Exception:
            continue

    return email_filled, pw_filled


async def _try_solve_recaptcha(tab) -> str:
    """Versucht reCAPTCHA-Checkbox zu klicken (passive Bypass).

    Returns 'passive_ok' | 'image_challenge' | 'blocked' | 'no_captcha' | 'unknown'.
    """
    await asyncio.sleep(1.5)

    # Pruef Verbindungs-Fail (Bot-Erkennung)
    try:
        body = await tab.evaluate("document.body.innerText")
        if body and "keine Verbindung zum reCAPTCHA" in body:
            return "blocked"
        if body and "reCAPTCHA-Dienst" in body and "Verbindung" in body:
            return "blocked"
    except Exception:
        pass

    # Suche reCAPTCHA-iframe
    try:
        iframes = await tab.evaluate(
            """Array.from(document.querySelectorAll('iframe'))
                .map(f => ({src: f.src, name: f.name, title: f.title}))
                .filter(f => f.src && f.src.indexOf('recaptcha') >= 0)"""
        )
        if not iframes:
            print(">>>   Kein reCAPTCHA-iframe", file=sys.stderr, flush=True)
            return "no_captcha"
        print(f">>>   reCAPTCHA-iframes: {len(iframes)}",
              file=sys.stderr, flush=True)
    except Exception as e:
        print(f">>>   iframe-Suche FAIL: {e}",
              file=sys.stderr, flush=True)

    # nodriver hat einen eingebauten reCAPTCHA-Checkbox-Klicker
    try:
        cb = await tab.find("I'm not a robot", best_match=True, timeout=4)
        if cb:
            await cb.click()
            await asyncio.sleep(3.0)
            print(">>>   reCAPTCHA-Checkbox geklickt (englisch)",
                  file=sys.stderr, flush=True)
    except Exception:
        pass
    try:
        cb = await tab.find("Ich bin kein Roboter", best_match=True, timeout=2)
        if cb:
            await cb.click()
            await asyncio.sleep(3.0)
            print(">>>   reCAPTCHA-Checkbox geklickt (deutsch)",
                  file=sys.stderr, flush=True)
    except Exception:
        pass

    # Pruef ob Image-Challenge aufgetaucht ist
    await asyncio.sleep(2.0)
    try:
        body = await tab.evaluate("document.body.innerText")
        if body and ("alle Bilder" in body or "Verkehrsschild" in body
                     or "Wähle alle" in body or "select all" in body.lower()):
            return "image_challenge"
        if body and "keine Verbindung" in body:
            return "blocked"
    except Exception:
        pass

    return "passive_ok"


async def _click_submit(tab) -> bool:
    for text in ["Login", "Anmelden", "Einloggen", "Einloggen anmelden"]:
        try:
            elem = await tab.find(text=text, best_match=True, timeout=2)
            if elem:
                await elem.click()
                print(f">>>   Submit via Text {text!r}",
                      file=sys.stderr, flush=True)
                await asyncio.sleep(3.0)
                return True
        except Exception:
            continue
    for sel in ['button[type="submit"]']:
        try:
            elem = await tab.query_selector(sel)
            if elem:
                await elem.click()
                print(f">>>   Submit via {sel}", file=sys.stderr, flush=True)
                await asyncio.sleep(3.0)
                return True
        except Exception:
            continue
    return False


async def _is_logged_in(tab) -> bool:
    """Heuristik: Login erfolgreich wenn URL geaendert, oder Logout-Link sichtbar."""
    try:
        url = tab.url
        if url and any(s in url.lower() for s in ["/dashboard", "/search",
                                                   "/suche", "/profil",
                                                   "/account", "/app"]):
            return True
    except Exception:
        pass
    for text in ["Logout", "Abmelden", "Mein Profil", "Mein Konto"]:
        try:
            elem = await tab.find(text=text, best_match=True, timeout=1)
            if elem:
                return True
        except Exception:
            continue
    return False


async def _export_cookies(browser) -> dict | None:
    try:
        cookies = await browser.cookies.get_all()
        out = {
            "exported_at": _ts(),
            "count": len(cookies),
            "cookies": [
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "secure": c.secure,
                    "http_only": c.http_only,
                    "expires": c.expires,
                }
                for c in cookies
            ],
        }
        COOKIES_OUT.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_OUT.write_text(
            json.dumps(out, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f">>> Cookies exportiert: {COOKIES_OUT} ({len(cookies)} cookies)",
              file=sys.stderr, flush=True)
        return out
    except Exception as e:
        print(f">>> Cookies-Export FAIL: {e}", file=sys.stderr, flush=True)
        return None


async def main_async() -> int:
    env = _load_env()
    user = env.get("IMMOMETRICA_USERNAME") or os.environ.get("IMMOMETRICA_USERNAME")
    pw = env.get("IMMOMETRICA_PASSWORD") or os.environ.get("IMMOMETRICA_PASSWORD")
    if not user or not pw:
        print(">>> FATAL: IMMOMETRICA_USERNAME/PASSWORD fehlen in .env",
              file=sys.stderr, flush=True)
        return 1

    import nodriver as uc

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    print(">>> Starte nodriver (Anti-Detect Chrome via CDP)",
          file=sys.stderr, flush=True)
    print(f">>> user_data_dir: {USER_DATA_DIR}",
          file=sys.stderr, flush=True)

    browser = await uc.start(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        lang="de-DE",
        browser_args=[
            "--lang=de-DE",
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
    )

    try:
        print(f">>> Lade {URL_HOME}", file=sys.stderr, flush=True)
        tab = await browser.get(URL_HOME)
        await asyncio.sleep(3.5)
        await _save_shot(tab, "01_home")

        # Cookies
        print(">>> Step 1: Cookie-Banner dismiss", file=sys.stderr, flush=True)
        await _dismiss_cookies(tab)
        await asyncio.sleep(1.0)

        # Newsletter-Modal
        print(">>> Step 2: Newsletter-Modal dismiss",
              file=sys.stderr, flush=True)
        await _dismiss_newsletter(tab)
        await asyncio.sleep(1.0)

        await _save_shot(tab, "02_after_dismiss")

        # Login-Button
        print(">>> Step 3: Login-Button klicken",
              file=sys.stderr, flush=True)
        clicked = await _click_login_button(tab)
        if not clicked:
            print(">>>   FAIL: Login-Button nicht gefunden",
                  file=sys.stderr, flush=True)
            await _save_shot(tab, "03_no_login_button")
            return 2
        await asyncio.sleep(2.5)
        await _save_shot(tab, "03_login_form")

        # Credentials eingeben
        print(">>> Step 4: E-Mail + Passwort eingeben",
              file=sys.stderr, flush=True)
        email_ok, pw_ok = await _fill_login_form(tab, user, pw)
        if not (email_ok and pw_ok):
            print(f">>>   FAIL: email={email_ok} pw={pw_ok}",
                  file=sys.stderr, flush=True)
            await _save_shot(tab, "04_form_incomplete")
            return 3
        await asyncio.sleep(1.0)
        await _save_shot(tab, "04_form_filled")

        # reCAPTCHA
        print(">>> Step 5: reCAPTCHA pruefen",
              file=sys.stderr, flush=True)
        captcha_status = await _try_solve_recaptcha(tab)
        print(f">>>   captcha_status = {captcha_status!r}",
              file=sys.stderr, flush=True)
        await _save_shot(tab, f"05_captcha_{captcha_status}")

        if captcha_status == "blocked":
            print(">>> reCAPTCHA blockt trotz nodriver. Versuche trotzdem Submit.",
                  file=sys.stderr, flush=True)
        elif captcha_status == "image_challenge":
            print(">>> reCAPTCHA Image-Challenge — kann nicht autonom geloest werden.",
                  file=sys.stderr, flush=True)
            print(">>> Lasse 30 Sekunden Zeit fuer manuelles Loesen...",
                  file=sys.stderr, flush=True)
            await asyncio.sleep(30)
            await _save_shot(tab, "05b_after_manual_solve_wait")

        # Submit
        print(">>> Step 6: Login-Button klicken", file=sys.stderr, flush=True)
        submitted = await _click_submit(tab)
        if not submitted:
            print(">>>   FAIL: Submit-Button nicht gefunden",
                  file=sys.stderr, flush=True)
            await _save_shot(tab, "06_no_submit")
            return 4
        await asyncio.sleep(5.0)
        await _save_shot(tab, "06_after_submit")

        # Login-Erfolg pruefen
        logged_in = await _is_logged_in(tab)
        try:
            print(f">>>   Aktuelle URL: {tab.url}",
                  file=sys.stderr, flush=True)
        except Exception:
            pass
        print(f">>>   Login-Erfolg: {logged_in}",
              file=sys.stderr, flush=True)

        if logged_in:
            print(">>> Step 7: Cookies exportieren",
                  file=sys.stderr, flush=True)
            await _export_cookies(browser)
            await _save_shot(tab, "07_dashboard")
            print(">>> LOGIN ERFOLGREICH", file=sys.stderr, flush=True)
            return 0
        else:
            print(">>> Login-Erfolg nicht eindeutig — exportiere trotzdem",
                  file=sys.stderr, flush=True)
            await _export_cookies(browser)
            await _save_shot(tab, "07_login_unclear")
            return 5

    except Exception as e:
        print(f">>> Exception: {e}\n{traceback.format_exc()}",
              file=sys.stderr, flush=True)
        return 99
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    import nodriver as uc

    return uc.loop().run_until_complete(main_async())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
