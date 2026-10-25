"""Submit-Form-Helpers — Warten auf Enabled-State + Klick mit Scroll-into-view."""
from __future__ import annotations

import time
from typing import Any

from core.log import log


def wait_for_enabled_submit(
    page: Any,
    submit_selector: str,
    max_wait_s: int = 60,
) -> bool:
    """Pollt bis der Submit-Button enabled ist.

    Wartet bis zu `max_wait_s` Sekunden — gibt dem User Zeit, falls
    automatisches Formular-Befüllen einen Pflicht-Klick verpasst hat.
    """
    btn = page.locator(submit_selector).first
    deadline = time.monotonic() + max_wait_s
    log(
        f"Falls Submit grau bleibt: bitte manuelles Eingreifen. "
        f"Tool wartet bis zu {max_wait_s} s."
    )
    last_status = None
    while time.monotonic() < deadline:
        try:
            enabled = btn.is_enabled(timeout=1_000)
            disabled_attr = btn.get_attribute("disabled")
            status = (enabled, disabled_attr)
            if status != last_status:
                remaining = int(deadline - time.monotonic())
                log(
                    f"Submit-Status: enabled={enabled} disabled-attr={disabled_attr!r} "
                    f"(noch {remaining} s)"
                )
                last_status = status
            if enabled and disabled_attr is None:
                log("Submit ist enabled.")
                return True
        except Exception:
            pass
        page.wait_for_timeout(1_000)
    log("Timeout — Submit blieb disabled.")
    return False


def click_submit(
    page: Any,
    submit_selector: str,
    *,
    scroll_settle_ms: int = 500,
    click_timeout_ms: int = 15_000,
) -> None:
    """Scrollt zum Submit-Button und klickt — wirft bei Timeout/Fehler weiter."""
    btn = page.locator(submit_selector).first
    btn.wait_for(state="visible", timeout=10_000)
    btn.scroll_into_view_if_needed()
    page.wait_for_timeout(scroll_settle_ms)
    log("Submit-Click läuft …")
    # force=True umgeht overlay-intercepts (z.B. CHECK24-Cookie-Akzeptieren-
    # Anker, der vor dem Submit-Button liegt). Analog zu core/inputs.py +
    # core/radios.py.
    btn.click(timeout=click_timeout_ms, force=True)
    log("Submit-Click ausgeführt.")
