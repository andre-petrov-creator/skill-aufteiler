"""Generic-Runner — orchestriert den gleichen Lebenszyklus für jedes Portal.

Browser → Cookies → fill_form → Submit-Enabled-Wait → Submit-Click →
Post-Submit-Modals → Result-Frame finden → Deep-Scroll → Body lesen →
parsen → JSON.

Aufteilung in `run_with_page()` (testbar mit FakePage) und `run()`
(public API mit Playwright-Lifecycle).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from core.cookies import dismiss_cookies
from core.datensatz import GeneralisierterDatensatz
from core.log import log, set_verbose
from core.parsers import (
    build_trend_label,
    parse_trends,
    trend_ampel,
)
from core.portal_base import PortalBase, RunConfig, RunResult
from core.reader import (
    deep_scroll_frame,
    find_result_frame,
    read_frame_body_deep,
    read_page_body_deep,
)
from core.submit import click_submit, wait_for_enabled_submit

BERLIN_TZ = timezone(timedelta(hours=2))


def _timestamp_iso() -> str:
    return datetime.now(BERLIN_TZ).isoformat(timespec="seconds")


def _ts_filename() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def _screenshot(page: Any, tag: str, runs_dir: Path) -> Optional[Path]:
    try:
        runs_dir.mkdir(parents=True, exist_ok=True)
        path = runs_dir / f"{_ts_filename()}_{tag}.png"
        page.screenshot(path=str(path), full_page=True)
        return path
    except Exception:
        return None


def _error_result(
    portal_name: str,
    step: str,
    exc: Exception,
    url: str,
    screenshot: Optional[Path],
) -> RunResult:
    return RunResult(
        status="error",
        portal=portal_name,
        url=url,
        timestamp=_timestamp_iso(),
        screenshot_path=str(screenshot) if screenshot else None,
        error_code=f"{step}_failed",
        error_message=f"{type(exc).__name__}: {exc}",
    )


def run_with_page(
    portal: PortalBase,
    datensatz: GeneralisierterDatensatz,
    page: Any,
    cfg: RunConfig,
    *,
    runs_dir: Optional[Path] = None,
) -> RunResult:
    """Innere Run-Logik — Page wird von außen bereitgestellt (für Tests + Live).

    Returns einen `RunResult`-Container, der per `.to_dict()` /
    `.to_json()` ins Output-Schema serialisiert wird.
    """
    set_verbose(cfg.verbose)
    started = _timestamp_iso()
    runs_dir = runs_dir or Path("runs")

    current_step = "init"
    try:
        current_step = "goto"
        page.goto(portal.START_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)

        current_step = "cookies"
        if portal.COOKIE_ACCEPT_CANDIDATES:
            dismiss_cookies(
                page,
                accept_candidates=portal.COOKIE_ACCEPT_CANDIDATES,
                wrapper_selector=portal.COOKIE_WRAPPER or None,
                max_wait_s=12.0,
            )

        current_step = "fill_form"
        portal.fill_form(page, datensatz, cfg)
        _screenshot(page, f"{portal.NAME}_after_fill", runs_dir)

        current_step = "submit"
        if portal.SUBMIT_SELECTOR:
            wait_for_enabled_submit(page, portal.SUBMIT_SELECTOR, max_wait_s=60)
            click_submit(page, portal.SUBMIT_SELECTOR)
        else:
            log(f"[{portal.NAME}] Kein SUBMIT_SELECTOR — Submit-Step übersprungen.")

        current_step = "post_submit_modals"
        portal.dismiss_post_submit_modals(page)

        current_step = "read_result"
        frame = find_result_frame(page, portal.RESULT_FRAME_MARKER)
        if frame is None:
            shot = _screenshot(page, f"{portal.NAME}_no_frame", runs_dir)
            return RunResult(
                status="error",
                portal=portal.NAME,
                url=getattr(page, "url", portal.START_URL),
                timestamp=started,
                screenshot_path=str(shot) if shot else None,
                error_code="result_frame_not_found",
                error_message=f"Kein Frame mit Marker {portal.RESULT_FRAME_MARKER!r}",
            )

        deep_scroll_frame(frame)
        body_text = read_frame_body_deep(frame)
        if not body_text:
            body_text = read_page_body_deep(page)

        marktwert = portal.parse_marktwert(body_text, page)
        trends = parse_trends(body_text)
        dom_colors = portal.extract_dom_colors(page)
        ampel, ampel_label = trend_ampel(trends, dom_colors=dom_colors or None)
        label = build_trend_label(
            marktwert=marktwert, trends=trends, ampel=ampel, ampel_label=ampel_label
        )
        extra = portal.extract_extra(body_text, page) or {}

        has_marktwert = marktwert["mittel"] is not None
        has_extra = any(v is not None for v in extra.values()) if extra else False

        shot = _screenshot(
            page,
            f"{portal.NAME}_result_{'ok' if (has_marktwert or has_extra) else 'empty'}",
            runs_dir,
        )

        if not has_marktwert and not has_extra:
            return RunResult(
                status="error",
                portal=portal.NAME,
                url=getattr(page, "url", portal.START_URL),
                timestamp=started,
                screenshot_path=str(shot) if shot else None,
                error_code="result_empty",
                error_message="Weder Marktwert noch Portal-Extras im Body-Text gefunden",
                raw_text_excerpt=body_text[:600],
                extra=extra,
            )

        if has_marktwert:
            log(
                f"[{portal.NAME}] Marktwert={marktwert['mittel']:,} €, "
                f"Trends={trends}, Ampel={ampel}".replace(",", ".")
            )
        else:
            log(f"[{portal.NAME}] Kein klassischer Marktwert, extras={list(extra.keys())}")

        return RunResult(
            status="ok",
            portal=portal.NAME,
            marktwert_eur_min=marktwert["min"],
            marktwert_eur_max=marktwert["max"],
            marktwert_eur_mittel=marktwert["mittel"],
            trends=trends,
            trend_ampel=ampel if has_marktwert else None,
            trend_ampel_label=ampel_label if has_marktwert else None,
            trend_label=label if has_marktwert else None,
            url=getattr(page, "url", portal.START_URL),
            timestamp=started,
            screenshot_path=str(shot) if shot else None,
            raw_text_excerpt=body_text[:600],
            extra=extra,
        )

    except Exception as e:
        shot = _screenshot(page, f"{portal.NAME}_error_{current_step}", runs_dir)
        return _error_result(
            portal.NAME,
            current_step,
            e,
            getattr(page, "url", portal.START_URL),
            shot,
        )


def run(
    portal: PortalBase,
    datensatz: GeneralisierterDatensatz,
    cfg: RunConfig,
    *,
    runs_dir: Optional[Path] = None,
) -> RunResult:
    """Public API — startet Playwright, ruft `run_with_page`, räumt auf."""
    from playwright.sync_api import sync_playwright

    from core.browser import launch_browser

    with sync_playwright() as p:
        browser, context, page = launch_browser(p, cfg.browser)
        try:
            return run_with_page(portal, datensatz, page, cfg, runs_dir=runs_dir)
        finally:
            try:
                context.close()
                browser.close()
            except Exception:
                pass
