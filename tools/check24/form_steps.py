"""Playwright-Flow für das CHECK24-Bewertungsformular.

Konsumiert einen GeneralisierterDatensatz und überträgt ihn in die 13 Form-Felder.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

try:
    from . import dom_selectors as sel
    from .generalisierter_datensatz import GeneralisierterDatensatz
except ImportError:
    import dom_selectors as sel  # type: ignore
    from generalisierter_datensatz import GeneralisierterDatensatz  # type: ignore

RUNS_DIR = Path(__file__).resolve().parent / "runs"
BERLIN_TZ = timezone(timedelta(hours=2))

_VERBOSE = False


def _log(msg: str) -> None:
    if _VERBOSE:
        import sys
        print(f">>> {msg}", flush=True, file=sys.stderr)


def set_verbose(verbose: bool) -> None:
    global _VERBOSE
    _VERBOSE = verbose


@dataclass
class RunConfig:
    headless: bool = False
    kaufabsicht: str = "kauf"
    verbose: bool = False


def _timestamp() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _screenshot(page: Page, tag: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{_timestamp()}_{tag}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def _cookies_present(page: Page) -> bool:
    try:
        wrapper = page.locator(sel.COOKIE_WRAPPER).first
        return wrapper.count() > 0 and wrapper.is_visible()
    except Exception:
        return False


def _accept_cookies_once(page: Page) -> bool:
    for selector in sel.COOKIE_ACCEPT_CANDIDATES:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3_000)
                return True
        except Exception:
            continue
    return False


def _ensure_cookies_dismissed(page: Page, max_wait_s: float = 15.0) -> None:
    """Wartet, bis das Cookie-Banner verschwindet — egal wann es aufpoppt."""
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        if not _cookies_present(page):
            return
        if _accept_cookies_once(page):
            page.wait_for_timeout(500)
            if not _cookies_present(page):
                return
        page.wait_for_timeout(400)
    try:
        page.evaluate(
            """
            document.querySelectorAll('.c24-cookie-consent-wrapper, .c24-strict-blocking-layer')
                .forEach(el => el.remove());
            """
        )
    except Exception:
        pass


def _select_by_index(page: Page, index: int, option_label: str) -> None:
    target = page.locator(sel.FORM_SELECTS).nth(index)
    target.wait_for(state="attached", timeout=5_000)
    target.select_option(label=option_label)
    page.wait_for_timeout(150)


def _input_typed(page: Page, index: int, value: str) -> None:
    target = page.locator(sel.FORM_INPUTS).nth(index)
    target.click()
    target.evaluate("el => el.value = ''")
    target.press_sequentially(value, delay=80)
    target.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))")
    target.press("Tab")
    page.wait_for_timeout(300)


def _normalize_strasse(value: str) -> str:
    """CHECK24 erwartet die Kurzform 'Str.' statt 'Straße/straße'."""
    normalized = re.sub(r"straße\b", "str.", value, flags=re.IGNORECASE)
    normalized = re.sub(r"strasse\b", "str.", normalized, flags=re.IGNORECASE)
    return normalized


def _input_street_with_autocomplete(page: Page, value: str, expected_match: str) -> bool:
    """Tippt die Straße (Kurzform Str.) und drückt Enter — CHECK24-Validierung.

    Vom User verifiziertes Verhalten: Tippen + Enter klappt, ABER
    'Straße' muss als 'Str.' geschrieben werden, sonst findet die
    Geo-Suche den Eintrag nicht.
    """
    short = _normalize_strasse(value)
    target = page.locator(sel.FORM_INPUTS).nth(sel.INPUT_STRASSE)
    target.click()
    target.evaluate("el => el.value = ''")
    target.press_sequentially(short, delay=120)
    page.wait_for_timeout(1800)
    target.press("Enter")
    page.wait_for_timeout(600)
    return True


def _click_radio(page: Page, qa_ref_selector: str, nudge_keys: bool = True) -> None:
    """Klickt ein Radio. CHECK24-Radios werden zwar fokussiert, aber NICHT
    visuell als selected markiert — wir müssen nach dem Klick eine Pfeiltaste
    drücken (rechts dann wieder links), damit der React-State 'angefasst'
    und korrekt aktiv wird.
    """
    ref_match = re.search(r'qa-ref="([^"]+)"', qa_ref_selector)
    if not ref_match:
        return
    ref = ref_match.group(1)

    label_locator = page.locator(f'xpath=//input[@qa-ref="{ref}"]/ancestor::label[1]')

    clicked = False
    try:
        label_locator.scroll_into_view_if_needed(timeout=3_000)
        page.wait_for_timeout(200)
        label_locator.click(timeout=5_000)
        clicked = True
    except PlaywrightTimeoutError:
        try:
            page.locator(qa_ref_selector).first.click(force=True, timeout=3_000)
            clicked = True
        except PlaywrightTimeoutError:
            pass

    if clicked and nudge_keys:
        page.wait_for_timeout(200)
        try:
            input_loc = page.locator(qa_ref_selector).first
            input_loc.evaluate("el => el.focus()")
            page.wait_for_timeout(150)
            for _ in range(2):
                page.keyboard.press("ArrowLeft")
                page.wait_for_timeout(120)
            for _ in range(2):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(120)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
        except Exception:
            pass
    page.wait_for_timeout(300)


def _fill_form(page: Page, d: GeneralisierterDatensatz, kaufabsicht: str) -> None:
    _select_by_index(page, sel.SELECT_IMMOTYP, sel.IMMOTYP_OPTION["wohnung"])
    _select_by_index(page, sel.SELECT_ZUSTAND, sel.ZUSTAND_OPTION[d.zustand])
    _select_by_index(page, sel.SELECT_AUSSTATTUNG, sel.AUSSTATTUNG_OPTION[d.ausstattung])

    _input_typed(page, sel.INPUT_PLZ, d.plz)

    strasse_match = d.strasse.replace("ß", "").replace("Straße", "").replace("straße", "").strip()
    strasse_match = (strasse_match[:8] if len(strasse_match) > 8 else strasse_match) or d.strasse[:6]
    _input_street_with_autocomplete(page, d.strasse, expected_match=strasse_match)

    _input_typed(page, sel.INPUT_HAUSNR, d.hausnr)
    _input_typed(page, sel.INPUT_WOHNFLAECHE, str(d.avg_wohnflaeche_qm))
    _input_typed(page, sel.INPUT_BAUJAHR, str(d.baujahr))
    _input_typed(page, sel.INPUT_ZIMMER, str(d.avg_zimmer))

    _select_by_index(page, sel.SELECT_BADEZIMMER, str(d.avg_badezimmer))
    _select_by_index(page, sel.SELECT_GARAGEN, "1" if d.hat_garage else "0")
    _select_by_index(page, sel.SELECT_AUSSENSTELLPLATZ, "1" if d.hat_aussenstellplatz else "0")

    radio_sel = sel.RADIO_KAUFEN if kaufabsicht == "kauf" else sel.RADIO_VERKAUFEN
    _click_radio(page, radio_sel, nudge_keys=False)
    page.wait_for_timeout(1_000)

    _click_zeitrahmen_1_3_monate(page)


def _click_zeitrahmen_1_3_monate(page: Page) -> None:
    """Klickt '1-3 Monate' per Text-Match und nudged mit Pfeiltasten,
    damit React-State den Klick als 'changed' registriert.

    Vom User verifiziert: Click → 2× ArrowRight → 2× ArrowLeft setzt den
    blauen Punkt und triggert die Form-Validation.
    """
    try:
        label_loc = page.locator('label:has-text("1-3 Monate")').first
        label_loc.scroll_into_view_if_needed(timeout=3_000)
        page.wait_for_timeout(200)
        label_loc.click(timeout=5_000)
        page.wait_for_timeout(400)
    except PlaywrightTimeoutError:
        try:
            page.get_by_text("1-3 Monate", exact=False).first.click(timeout=3_000)
            page.wait_for_timeout(400)
        except Exception:
            return

    for _ in range(2):
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(120)
    for _ in range(2):
        page.keyboard.press("ArrowLeft")
        page.wait_for_timeout(120)
    page.wait_for_timeout(400)


def _wait_for_enabled_submit(page: Page, max_wait_s: int = 120) -> bool:
    """Wartet bis Submit-Button enabled ist — gibt dem User Zeit, manuell
    den Zeitrahmen-Radio zu klicken, falls die Automation das nicht schafft.
    """
    btn = page.locator(sel.SUBMIT_BUTTON).first
    deadline = time.monotonic() + max_wait_s
    _log(
        f"Falls 'Immobilienwert schätzen' grau bleibt: bitte manuell "
        f"im Browser auf '1-3 Monate' klicken. Tool wartet bis zu {max_wait_s} s."
    )
    last_status = None
    while time.monotonic() < deadline:
        try:
            enabled = btn.is_enabled(timeout=1_000)
            disabled_attr = btn.get_attribute("disabled")
            status = (enabled, disabled_attr)
            if status != last_status:
                remaining = int(deadline - time.monotonic())
                _log(
                    f"Submit-Status: enabled={enabled} disabled-attr={disabled_attr!r} "
                    f"(noch {remaining} s)"
                )
                last_status = status
            if enabled and disabled_attr is None:
                _log("Submit ist enabled — klicke jetzt.")
                return True
        except Exception:
            pass
        page.wait_for_timeout(1_000)
    _log("Timeout — Submit blieb disabled.")
    return False


def _dismiss_topzinsen_modal(page: Page) -> bool:
    """Klickt 'später erinnern' im Topzinsen-Modal. Returns True wenn geklickt."""
    candidates = [
        'button:has-text("später erinnern")',
        'button:has-text("Später erinnern")',
        'a:has-text("später erinnern")',
        '[role="button"]:has-text("später erinnern")',
    ]
    for sel_str in candidates:
        try:
            loc = page.locator(sel_str).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=3_000)
                page.wait_for_timeout(800)
                _log("Topzinsen-Modal mit 'später erinnern' geschlossen.")
                return True
        except Exception:
            continue
    return False


def _click_submit(page: Page) -> None:
    btn = page.locator(sel.SUBMIT_BUTTON).first
    btn.wait_for(state="visible", timeout=10_000)
    btn.scroll_into_view_if_needed()
    page.wait_for_timeout(500)

    _log("Submit-Click läuft …")
    btn.click(timeout=15_000)
    _log("Submit-Click ausgeführt. Warte auf Ergebnis-Seite …")

    deadline = time.monotonic() + 60
    modal_dismissed = False
    while time.monotonic() < deadline:
        page.wait_for_timeout(1_500)

        if not modal_dismissed:
            if _dismiss_topzinsen_modal(page):
                modal_dismissed = True
                page.wait_for_timeout(800)
                _dismiss_second_cookie(page)

        for frame in page.frames:
            try:
                if frame.locator("text=Marktwertermittlung").count() > 0:
                    print(
                        f">>> Marktwertermittlung-Block in Frame gefunden: {frame.url[:80]}",
                        flush=True,
                    )
                    return
            except Exception:
                continue
    _log("Timeout beim Warten auf Marktwert-Block.")


def _dismiss_second_cookie(page: Page) -> None:
    """Zweites Cookie-Banner unten ('OK')."""
    candidates = [
        'button:has-text("OK"):visible',
        'button[aria-label="OK"]',
    ]
    for c in candidates:
        try:
            loc = page.locator(c).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=2_000)
                page.wait_for_timeout(400)
                _log("Zweites Cookie-Banner mit OK geschlossen.")
                return
        except Exception:
            continue


def _euro_to_int(s: str) -> Optional[int]:
    digits = re.sub(r"[.\s]", "", s)
    return int(digits) if digits.isdigit() else None


def _parse_marktwert_block(text: str) -> dict[str, Optional[int]]:
    """Extrahiert Mittelwert und Spanne aus dem 'Marktwertermittlung'-Block."""
    mittel = None
    min_v = None
    max_v = None

    m_mittel = re.search(r"Marktwert[\s\n|]+(\d{1,3}(?:[.\s]\d{3})+)\s*€", text)
    if m_mittel:
        mittel = _euro_to_int(m_mittel.group(1))

    m_spanne = re.search(
        r"Marktwertspanne[\s\n|]+(\d{1,3}(?:[.\s]\d{3})+)[\s\n|]*-?[\s\n|]*(\d{1,3}(?:[.\s]\d{3})+)\s*€",
        text,
    )
    if m_spanne:
        min_v = _euro_to_int(m_spanne.group(1))
        max_v = _euro_to_int(m_spanne.group(2))

    return {"min": min_v, "max": max_v, "mittel": mittel}


def _parse_trends(text: str) -> dict[str, Optional[float]]:
    """Extrahiert die drei Trend-Prozente aus dem Zeitverlauf-Block.

    Echtes CHECK24/PriceHubble-Format hat drei Trend-Labels:
      'In den letzten 3 Jahren'
      'Seit letztem Jahr'
      'Prognose für das nächste Jahr'

    Vor jedem Label steht ein Block der Form `[+-]? <zahl> % (<absolut>)`.
    Wir suchen pro Label rückwärts den passenden Prozent-Wert.
    """
    out: dict[str, Optional[float]] = {"jahre_3": None, "jahr_1": None, "prognose": None}

    labels = [
        ("jahre_3", re.compile(r"(?:In\s+den\s+)?letzten\s+3\s+Jahren?", re.IGNORECASE)),
        ("jahr_1", re.compile(r"Seit\s+letztem\s+Jahr", re.IGNORECASE)),
        ("prognose", re.compile(r"Prognose\s+f[uü]r\s+das\s+n[aä]chste\s+Jahr", re.IGNORECASE)),
    ]

    percent_pat = re.compile(r"([+-])?\s*\|?\s*(\d+[,.]?\d*)\s*%")

    for key, label_re in labels:
        m = label_re.search(text)
        if not m:
            continue
        before = text[: m.start()]
        percents = list(percent_pat.finditer(before))
        if not percents:
            continue
        last = percents[-1]
        sign = (last.group(1) or "").strip()
        num = last.group(2)
        value = float(num.replace(",", "."))
        if sign == "-":
            value = -value
        out[key] = value

    return out


def _read_trend_colors(page: Page) -> dict[str, Optional[str]]:
    """Liest die CHECK24-eigenen Ampel-Farben aus dem DOM.

    CHECK24 färbt Trend-Werte selbst — grün/gelb/rot ist im class-Attribut
    oder im style.color des Prozent-Span. Wir nutzen das als Quervalidierung.
    """
    try:
        colors = page.evaluate(
            """() => {
                const out = {jahre_3: null, jahr_1: null, prognose: null};
                const labels = [
                    {key: 'jahre_3', match: ['3 Jahren', 'letzten 3']},
                    {key: 'jahr_1', match: ['letztem Jahr', 'Seit letztem']},
                    {key: 'prognose', match: ['Prognose', 'nächste']},
                ];
                document.querySelectorAll('*').forEach(el => {
                    const txt = (el.textContent || '').trim();
                    if (txt.length > 200) return;
                    for (const lbl of labels) {
                        if (lbl.match.some(m => txt.includes(m)) && out[lbl.key] === null) {
                            const container = el.closest('div, li, section') || el.parentElement;
                            if (!container) continue;
                            const percentEl = container.querySelector('[class*="green"], [class*="yellow"], [class*="red"], [class*="positive"], [class*="negative"], [style*="color"]');
                            if (percentEl) {
                                const cls = (percentEl.className || '').toString().toLowerCase();
                                const style = (percentEl.getAttribute('style') || '').toLowerCase();
                                if (cls.includes('green') || cls.includes('positive') || style.includes('green')) out[lbl.key] = 'gruen';
                                else if (cls.includes('yellow') || cls.includes('orange') || style.includes('yellow') || style.includes('orange')) out[lbl.key] = 'gelb';
                                else if (cls.includes('red') || cls.includes('negative') || style.includes('red')) out[lbl.key] = 'rot';
                            }
                        }
                    }
                });
                return out;
            }"""
        )
        return colors or {"jahre_3": None, "jahr_1": None, "prognose": None}
    except Exception:
        return {"jahre_3": None, "jahr_1": None, "prognose": None}


def _trend_ampel(
    trends: dict[str, Optional[float]],
    dom_colors: Optional[dict[str, Optional[str]]] = None,
) -> tuple[str, str]:
    """Liefert (ampel, label) basierend auf Trend-Werten + optional CHECK24-DOM-Farben.

    Eigene Schwellen:
      ROT   = Prognose negativ ODER (jahr_1 < 0 UND jahre_3 < 0)
      GELB  = stagnierend: |3J| < 2% und |1J| < 1.5%, oder Prognose ≤ 1%
      GRÜN  = sonst (überwiegend positiv)

    Wenn dom_colors verfügbar: CHECK24-eigene Farben überschreiben unsere
    Heuristik (Quervalidierung). Mehrheitsentscheid bei mehreren Farben.
    """
    j3 = trends.get("jahre_3")
    j1 = trends.get("jahr_1")
    pg = trends.get("prognose")

    if dom_colors:
        votes = [c for c in dom_colors.values() if c]
        if votes:
            from collections import Counter
            top, _ = Counter(votes).most_common(1)[0]
            labels = {"gruen": "steigend (CHECK24)", "gelb": "stagnierend (CHECK24)", "rot": "fallend (CHECK24)"}
            return top, labels[top]

    if pg is not None and pg < 0:
        return "rot", "fallend (Prognose negativ)"
    if j1 is not None and j3 is not None and j1 < 0 and j3 < 0:
        return "rot", "fallend (1-J + 3-J negativ)"

    stagnant = (
        (j3 is not None and abs(j3) < 2.0 and j1 is not None and abs(j1) < 1.5)
        or (pg is not None and pg <= 1.0)
    )
    if stagnant:
        return "gelb", "stagnierend"

    return "gruen", "steigend"


def _build_trend_label(marktwert: dict, trends: dict, ampel: str, ampel_label: str) -> str:
    parts = ["CHECK24 PriceHugger:"]
    if marktwert.get("min") and marktwert.get("max"):
        parts.append(f"Marktwert {marktwert['min']:,} – {marktwert['max']:,} €".replace(",", "."))
    if marktwert.get("mittel"):
        parts.append(f"(Mittel {marktwert['mittel']:,} €)".replace(",", "."))
    emoji = {"gruen": "🟢", "gelb": "🟡", "rot": "🔴"}.get(ampel, "")
    parts.append(f"Trend {emoji} {ampel_label}")
    detail = []
    if trends.get("jahre_3") is not None:
        detail.append(f"{trends['jahre_3']:+.1f}% 3J")
    if trends.get("jahr_1") is not None:
        detail.append(f"{trends['jahr_1']:+.1f}% 1J")
    if trends.get("prognose") is not None:
        detail.append(f"{trends['prognose']:+.1f}% Prognose")
    if detail:
        parts.append("(" + " / ".join(detail) + ")")
    return " ".join(parts)


def _dismiss_result_modals(page: Page) -> None:
    """Klickt 'später erinnern' beim Topzinsen-Modal und 'OK' beim zweiten Cookie-Banner."""
    for selector_list in (sel.RESULT_MODAL_DISMISS, sel.RESULT_COOKIE_OK):
        for selector in selector_list:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=3_000)
                    page.wait_for_timeout(600)
                    break
            except Exception:
                continue


def _read_result(page: Page) -> dict:
    _dismiss_result_modals(page)
    page.wait_for_timeout(500)

    iframe_count = page.locator("iframe").count()
    if iframe_count:
        _log(f"{iframe_count} iframe(s) auf der Seite — durchsuche.")

    body_text = ""
    target_frame = None

    for frame in page.frames:
        try:
            text = frame.locator("body").inner_text(timeout=2_000)
        except Exception:
            continue
        if "Marktwertermittlung" in text or "Marktwertspanne" in text:
            target_frame = frame
            print(
                f">>> Marktwert-iframe gefunden: {frame.url[:80]}",
                flush=True,
            )
            break

    if target_frame is not None:
        for _ in range(3):
            _dismiss_topzinsen_modal(page)
            page.wait_for_timeout(500)

        try:
            target_frame.evaluate(
                """() => {
                    return new Promise(resolve => {
                        const findScrollable = () => {
                            const els = Array.from(document.querySelectorAll('*'));
                            return els.filter(el => {
                                const cs = getComputedStyle(el);
                                return (cs.overflowY === 'auto' || cs.overflowY === 'scroll')
                                    && el.scrollHeight > el.clientHeight + 50;
                            });
                        };
                        let step = 0;
                        const iv = setInterval(() => {
                            const scrollables = findScrollable();
                            scrollables.forEach(el => { el.scrollTop = el.scrollTop + 800; });
                            window.scrollBy(0, 800);
                            step++;
                            if (step >= 20) { clearInterval(iv); resolve(); }
                        }, 250);
                    });
                }"""
            )
            page.wait_for_timeout(1_500)
        except Exception as e:
            _log(f"Frame-Scroll fehlgeschlagen: {e}")

        for _ in range(3):
            _dismiss_topzinsen_modal(page)
            page.wait_for_timeout(400)

        try:
            body_text = target_frame.evaluate(
                """() => {
                    const allText = [];
                    document.querySelectorAll('*').forEach(el => {
                        const cs = getComputedStyle(el);
                        if (cs.display === 'none' || cs.visibility === 'hidden') return;
                        const own = Array.from(el.childNodes)
                            .filter(n => n.nodeType === 3)
                            .map(n => n.textContent.trim()).filter(t => t).join(' ');
                        if (own) allText.push(own);
                    });
                    return allText.join('\\n');
                }"""
            )
            _log(f"Deep iframe-Body nach Scroll: {len(body_text)} Zeichen.")
            if "Zeitverlauf" in body_text:
                idx = body_text.index("Zeitverlauf")
                snippet = body_text[idx:idx + 800].replace("\n", " | ")
                _log(f"Trend-Snippet: {snippet}")
        except Exception:
            pass

    if not body_text:
        try:
            body_text = page.evaluate(
                """() => {
                    function collect(root) {
                        let texts = [];
                        root.querySelectorAll('*').forEach(el => {
                            if (el.shadowRoot) texts.push(el.shadowRoot.textContent || '');
                            const cs = getComputedStyle(el);
                            if (cs.display !== 'none' && cs.visibility !== 'hidden') {
                                const own = Array.from(el.childNodes)
                                    .filter(n => n.nodeType === 3)
                                    .map(n => n.textContent).join(' ');
                                if (own.trim()) texts.push(own);
                            }
                        });
                        return texts.join('\\n');
                    }
                    return collect(document.body);
                }"""
            )
            _log(f"Deep-DOM-Collection Text-Länge: {len(body_text)}")
        except Exception:
            body_text = page.locator("body").inner_text()
    marktwert = _parse_marktwert_block(body_text)
    trends = _parse_trends(body_text)
    dom_colors = _read_trend_colors(page)
    ampel, ampel_label = _trend_ampel(trends, dom_colors)
    label = _build_trend_label(marktwert, trends, ampel, ampel_label)

    return {
        "text": body_text[:2000],
        **marktwert,
        "trends": trends,
        "trend_check24_colors": dom_colors,
        "trend_ampel": ampel,
        "trend_ampel_label": ampel_label,
        "trend_label": label,
    }


def run(d: GeneralisierterDatensatz, cfg: RunConfig) -> dict:
    set_verbose(cfg.verbose)
    started = datetime.now(BERLIN_TZ).isoformat(timespec="seconds")
    with sync_playwright() as p:  # type: Playwright
        browser = p.chromium.launch(headless=cfg.headless)
        context = browser.new_context(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            viewport={"width": 1440, "height": 1600},
        )
        page = context.new_page()
        page.set_default_timeout(sel.TIMEOUT_MS_DEFAULT)

        current_step = "init"
        try:
            page.goto(sel.START_URL, wait_until="domcontentloaded")
            current_step = "cookies"
            page.wait_for_timeout(2_000)
            _ensure_cookies_dismissed(page, max_wait_s=12.0)

            current_step = "fill_form"
            page.wait_for_selector(sel.FORM_SELECTS, timeout=sel.TIMEOUT_MS_DEFAULT)
            _ensure_cookies_dismissed(page, max_wait_s=3.0)
            _fill_form(page, d, cfg.kaufabsicht)
            _screenshot(page, "after_fill")

            current_step = "submit"
            _wait_for_enabled_submit(page, max_wait_s=60)
            _click_submit(page)

            current_step = "result"
            result = _read_result(page)
            shot = _screenshot(page, "result_ok" if result["mittel"] else "result_empty")

            if not result["mittel"]:
                return {
                    "status": "error",
                    "error_code": "result_empty",
                    "error_message": "Kein Marktwert in Ergebnistext gefunden",
                    "result_text": result["text"],
                    "url": page.url,
                    "timestamp": started,
                    "screenshot_path": str(shot.relative_to(RUNS_DIR.parent)),
                }
            return {
                "status": "ok",
                "marktwert_eur_min": result["min"],
                "marktwert_eur_max": result["max"],
                "marktwert_eur_mittel": result["mittel"],
                "trends": result.get("trends"),
                "trend_ampel": result.get("trend_ampel"),
                "trend_ampel_label": result.get("trend_ampel_label"),
                "trend_label": result.get("trend_label"),
                "result_text": result["text"][:600],
                "url": page.url,
                "timestamp": started,
                "screenshot_path": str(shot.relative_to(RUNS_DIR.parent)),
            }
        except Exception as e:
            shot_path: Optional[str] = None
            try:
                shot = _screenshot(page, f"error_{current_step}")
                shot_path = str(shot.relative_to(RUNS_DIR.parent))
            except Exception:
                pass
            return {
                "status": "error",
                "error_code": f"{current_step}_failed",
                "error_message": f"{type(e).__name__}: {e}",
                "url": page.url if page else sel.START_URL,
                "timestamp": started,
                "screenshot_path": shot_path,
            }
        finally:
            context.close()
            browser.close()
