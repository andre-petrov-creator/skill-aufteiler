"""
Capability-Stages fuer Universal Link Fetcher.
Stage 1: Playwright headless Stealth (Default, billig)
Stage 2: nodriver (sichtbares Fenster, gegen Imperva/Cloudflare-Captcha)
Stage 3: 2Captcha (kostenpflichtig, nur fuer ImmoScout24)
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


CAPTCHA_MARKERS = [
    r"ich\s+bin\s+kein\s+roboter",                     # Imperva-Block (DE)
    r"pardon\s+our\s+interruption",                    # Imperva-Block (EN)
    r"sorry,?\s*you\s+have\s+been\s+blocked",          # Cloudflare/generisch
    r"checking\s+your\s+browser\s+before",             # Cloudflare-Challenge
    r"attention\s+required.{0,40}cloudflare",          # Cloudflare-Block-Title
    r"verify\s+you\s+are\s+human",                     # hCaptcha/generisch
    r"are\s+you\s+human\?",                            # Datadome
    r"_incapsula_resource",                            # Imperva-CSS-Marker
    r"just\s+a\s+moment\.\.\..{0,200}cf[-_]chl",       # Cloudflare-Interstitial
]

SHORT_BODY_THRESHOLD = 5_000


def has_captcha_marker(html: str | None) -> bool:
    """True wenn HTML als Captcha-/Block-Seite erkennbar ist.

    Heuristik: ein Block-Marker reicht (sind alle spezifisch genug).
    Reine reCAPTCHA-Library-Einbindung in Forms triggert NICHT — die
    erkennbar an `data-sitekey=` oder `recaptcha/api.js` ohne Block-String.
    """
    if not html:
        return False
    lower = html.lower()
    if any(re.search(p, lower) for p in CAPTCHA_MARKERS):
        return True
    # Sehr kurzes HTML + sitekey ohne sonstigen Content = Challenge-Seite
    if len(html) < SHORT_BODY_THRESHOLD and re.search(r'data-sitekey=', lower):
        return True
    return False


def is_likely_property_image(url: str) -> bool:
    """Filter: hohe Wahrscheinlichkeit ein Objektbild (kein Logo/Icon)."""
    if not url or url.startswith("data:"):
        return False
    u = url.lower()
    for skip in ["logo", "icon", "avatar", "favicon", "social",
                 "facebook", "instagram", "linkedin"]:
        if skip in u:
            return False
    if any(k in u for k in ["cloudfront", "amazonaws", "/listing/",
                            "/expose/", "/property/", "/immobilie/"]):
        return True
    if (u.endswith((".jpg", ".jpeg", ".png", ".webp")) and len(u) > 80):
        return True
    return False


def _capture_downloads(page, output_dir: Path,
                       timeout_per_click_ms: int = 30_000) -> int:
    """
    Findet Download-Trigger auf der Page und holt die Files lokal.
    Generisch — funktioniert bei onOffice-Wrapper-Seiten (onclick=openFile),
    direkten PDF-Links (a[href$=".pdf"]) und einfachen Download-Buttons.
    Skipped "Alle herunterladen"-Bundle-Buttons (duplizieren Einzeldateien).

    Speichert mit `suggested_filename` aus dem Download-Event (Browser-seitig),
    bzw. mit dem Basename aus href. Returns Anzahl gespeicherter Files.
    """
    saved = 0
    seen = set()

    direct_selectors = [
        'a[href$=".pdf"]', 'a[href$=".PDF"]',
        'a[href$=".docx"]', 'a[href$=".doc"]',
        'a[href$=".xlsx"]', 'a[href$=".xls"]',
        'a[href$=".zip"]',
    ]
    for sel in direct_selectors:
        try:
            links = page.locator(sel).all()
        except Exception:
            continue
        for link in links:
            try:
                href = link.get_attribute("href")
                if not href or href in seen:
                    continue
                seen.add(href)
                if href.startswith(("http://", "https://")):
                    target_url = href
                else:
                    from urllib.parse import urljoin
                    target_url = urljoin(page.url, href)
                cookies = page.context.cookies()
                sess = requests.Session()
                for c in cookies:
                    sess.cookies.set(c["name"], c["value"],
                                     domain=c.get("domain"))
                r = sess.get(target_url, timeout=60, allow_redirects=True)
                if r.ok and len(r.content) > 1000:
                    name = href.split("/")[-1].split("?")[0]
                    if not name or "." not in name:
                        name = f"download_{saved+1}.bin"
                    (output_dir / name).write_bytes(r.content)
                    saved += 1
            except Exception:
                continue

    click_selectors = [
        '[onclick*="openFile"]',
        '[onclick*="downloadFile"]',
        '[onclick*="getFile"]',
        '[onclick*="download_file"]',
    ]
    for sel in click_selectors:
        try:
            elements = page.locator(sel).all()
        except Exception:
            continue
        for el in elements:
            try:
                onclick = el.get_attribute("onclick") or ""
                if not onclick or onclick in seen:
                    continue
                seen.add(onclick)
                el_text = (el.inner_text() or "").strip().lower()
                if "alle herunter" in el_text or "download all" in el_text:
                    continue
                with page.expect_download(timeout=timeout_per_click_ms) as info:
                    el.click()
                d = info.value
                suggested = d.suggested_filename or f"download_{saved+1}.bin"
                d.save_as(str(output_dir / suggested))
                saved += 1
            except Exception:
                continue

    return saved


def _collect_and_download_images(page, output_dir: Path) -> int:
    """Sammelt Bild-URLs auf der Page, filtert + speichert nach output_dir/bilder/."""
    urls = page.evaluate("""
    () => {
      const out = new Set();
      document.querySelectorAll('img').forEach(img => {
        if (img.src) out.add(img.src);
        if (img.srcset) {
          img.srcset.split(',').forEach(s => {
            const u = s.trim().split(' ')[0];
            if (u) out.add(u);
          });
        }
      });
      document.querySelectorAll('[style*="background-image"]').forEach(el => {
        const m = el.style.backgroundImage.match(/url\\(['"]?(.*?)['"]?\\)/);
        if (m) out.add(m[1]);
      });
      return Array.from(out);
    }
    """)
    keepers = [u for u in urls if is_likely_property_image(u)]
    if not keepers:
        return 0
    bilder_dir = output_dir / "bilder"
    bilder_dir.mkdir(exist_ok=True)
    saved = 0
    for i, u in enumerate(keepers, start=1):
        try:
            r = requests.get(u, timeout=30)
            r.raise_for_status()
            if len(r.content) < 5000:
                continue
            ext = u.split("?")[0].split(".")[-1].lower()
            if ext not in ("jpg", "jpeg", "png", "webp"):
                ext = "jpg"
            (bilder_dir / f"bild_{i:02d}.{ext}").write_bytes(r.content)
            saved += 1
        except Exception:
            continue
    return saved


def stage1_playwright_headless(url: str, output_dir: Path) -> tuple[bool, str]:
    """
    Default-Stufe: Playwright Chromium headless mit Stealth-Tweaks.
    Schreibt: <output_dir>/web-expose.html, web-expose-screenshot.png,
              Exposé Webseite.pdf, bilder/bild_NN.jpg, final_url.txt
    Returns: (success, html_content_or_error_message)
    """
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 2400},
                accept_downloads=True,
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except Exception:
                pass
            for y in range(0, 8000, 600):
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(300)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(2000)

            html = page.content()
            (output_dir / "web-expose.html").write_text(html, encoding="utf-8")
            (output_dir / "final_url.txt").write_text(page.url, encoding="utf-8")
            page.screenshot(path=str(output_dir / "web-expose-screenshot.png"),
                            full_page=True)
            try:
                page.emulate_media(media="print")
                page.pdf(path=str(output_dir / "Exposé Webseite.pdf"),
                         format="A4", print_background=True)
                page.emulate_media(media="screen")
            except Exception:
                pass
            _collect_and_download_images(page, output_dir)
            _capture_downloads(page, output_dir)
            browser.close()
            return (True, html)
    except Exception as e:
        return (False, f"Stage1 error: {type(e).__name__}: {e}")


def stage2_nodriver(url: str, output_dir: Path) -> tuple[bool, str]:
    """
    Eskalation: nodriver (sichtbares Browser-Fenster) gegen Imperva/Cloudflare.
    Portiert aus immoscout/stages/stage3_nodriver.py — generisch gemacht.
    """
    return asyncio.run(_stage2_nodriver_async(url, output_dir))


async def _stage2_nodriver_async(url: str, output_dir: Path) -> tuple[bool, str]:
    import nodriver as uc

    output_dir.mkdir(parents=True, exist_ok=True)
    settle_seconds = 8.0
    browser = None
    try:
        browser = await uc.start(headless=False)
        page = await browser.get(url)
        await asyncio.sleep(settle_seconds)
        html = await page.get_content()
        final_url = await page.evaluate("document.location.href") or url
        (output_dir / "web-expose.html").write_text(html, encoding="utf-8")
        (output_dir / "final_url.txt").write_text(final_url, encoding="utf-8")
        try:
            await page.save_screenshot(str(output_dir / "web-expose-screenshot.png"),
                                       full_page=True)
        except Exception:
            pass
        return (True, html)
    except Exception as e:
        return (False, f"Stage2 error: {type(e).__name__}: {e}")
    finally:
        if browser is not None:
            try:
                browser.stop()
            except Exception:
                pass


def stage3_2captcha(url: str, output_dir: Path) -> tuple[bool, str]:
    """
    Letzte Stufe: 2Captcha-Service (kostenpflichtig). NUR fuer ImmoScout24.
    Portiert aus immoscout/stages/stage5_2captcha.py — schreibt expose.json
    als Bonus-Output (Telekom-base64-Adresse + Kaufpreis).
    """
    api_key = os.environ.get("TWOCAPTCHA_API_KEY", "").strip()
    if not api_key:
        return (False, "TWOCAPTCHA_API_KEY not set — Stage 3 disabled")
    return asyncio.run(_stage3_2captcha_async(url, output_dir, api_key))


async def _stage3_2captcha_async(url: str, output_dir: Path, api_key: str) -> tuple[bool, str]:
    import nodriver as uc
    from twocaptcha import TwoCaptcha

    output_dir.mkdir(parents=True, exist_ok=True)
    settle_seconds = 5.0
    browser = None
    try:
        solver = TwoCaptcha(api_key)
        browser = await uc.start(headless=True)
        page = await browser.get(url)
        await asyncio.sleep(settle_seconds)
        html = await page.get_content()

        sitekey_match = re.search(r'data-sitekey="([^"]+)"', html)
        if sitekey_match:
            sitekey = sitekey_match.group(1)
            try:
                captured = solver.hcaptcha(sitekey=sitekey, url=url)
            except Exception:
                captured = solver.recaptcha(sitekey=sitekey, url=url)
            token = captured.get("code", "")
            if token:
                await page.evaluate(
                    f'document.querySelector("[name=h-captcha-response]") && '
                    f'(document.querySelector("[name=h-captcha-response]").value = "{token}");'
                )
                await page.evaluate(
                    f'document.querySelector("[name=g-recaptcha-response]") && '
                    f'(document.querySelector("[name=g-recaptcha-response]").value = "{token}");'
                )
                await page.evaluate(
                    "document.querySelector('form') && document.querySelector('form').submit();"
                )
                await asyncio.sleep(settle_seconds)
                html = await page.get_content()

        final_url = await page.evaluate("document.location.href") or url
        (output_dir / "web-expose.html").write_text(html, encoding="utf-8")
        (output_dir / "final_url.txt").write_text(final_url, encoding="utf-8")
        try:
            await page.save_screenshot(str(output_dir / "web-expose-screenshot.png"),
                                       full_page=True)
        except Exception:
            pass

        _write_immoscout_expose_json(url, html, final_url, output_dir)
        return (True, html)
    except Exception as e:
        return (False, f"Stage3 error: {type(e).__name__}: {e}")
    finally:
        if browser is not None:
            try:
                browser.stop()
            except Exception:
                pass


def _write_immoscout_expose_json(url: str, html: str, final_url: str,
                                  output_dir: Path) -> None:
    """Bonus-Output fuer ImmoScout: ruft den bestehenden Parser auf."""
    try:
        import json
        import sys
        portal_root = Path(__file__).resolve().parent.parent / "portal-bewertung"
        if str(portal_root) not in sys.path:
            sys.path.insert(0, str(portal_root))
        from immoscout.parser import extract_keyvalues, parse_expose  # noqa: E402

        kv = extract_keyvalues(html)
        expose = parse_expose(html=html, final_url=final_url)
        expose["successful_stage"] = "stage3_2captcha"
        (output_dir / "expose.json").write_text(
            json.dumps(expose, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if kv:
            (output_dir / "expose_keyvalues.json").write_text(
                json.dumps(kv, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except Exception:
        # Bonus-Output: bei Parser-Fehler einfach ohne expose.json weitermachen
        pass
