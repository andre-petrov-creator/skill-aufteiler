"""Probe: was passiert genau nach Trash-Click? Confirmation-Dialog?"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJ_ROOT = Path(__file__).resolve().parent.parent
USER_DATA_DIR = PROJ_ROOT / "learned_selectors" / "immometrica_nodriver_userdata"


async def main_async() -> int:
    import nodriver as uc
    browser = await uc.start(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        lang="de-DE",
        browser_args=["--lang=de-DE", "--disable-blink-features=AutomationControlled"],
    )
    try:
        tab = await browser.get("https://www.immometrica.com/de/statistics")
        await asyncio.sleep(6.0)

        # State davor
        before = await tab.evaluate(
            """(() => {
                const widget = document.querySelector('.location-select-widget');
                return widget ? widget.innerText.trim().slice(0,200) : 'no widget';
            })()"""
        )
        if isinstance(before, dict) and "value" in before:
            before = before["value"]
        print(f">>> VOR Trash:\n{before}\n", file=sys.stderr, flush=True)

        # Trash-Click
        clicked = await tab.evaluate(
            """(() => {
                const widget = document.querySelector('.location-select-widget');
                if (!widget) return 0;
                let n = 0;
                const trashes = widget.querySelectorAll('a > i.fa-trash, a > i.fas.fa-trash');
                for (const ico of trashes) {
                    const a = ico.closest('a');
                    if (a) { a.click(); n++; }
                }
                return n;
            })()"""
        )
        if isinstance(clicked, dict) and "value" in clicked:
            clicked = clicked["value"]
        print(f">>> Trash geklickt: {clicked}", file=sys.stderr, flush=True)

        await asyncio.sleep(0.5)

        # State direkt nach Click (Dialog?)
        for delay in [0.5, 1.0, 2.0]:
            await asyncio.sleep(delay)
            cumulative = sum([0.5, 0.5, 1.0, 2.0])  # logging
            state = await tab.evaluate(
                """(() => {
                    const dialogs = Array.from(document.querySelectorAll(
                        '.modal, [role="dialog"], .swal2-popup, .alert'
                    )).filter(d => d.offsetParent !== null);
                    const widget = document.querySelector('.location-select-widget');
                    return JSON.stringify({
                        dialogs: dialogs.map(d => d.innerText.trim().slice(0, 200)),
                        widget: widget ? widget.innerText.trim().slice(0, 200) : 'no widget'
                    });
                })()"""
            )
            if isinstance(state, dict) and "value" in state:
                state = state["value"]
            print(f">>> Nach +{delay}s:\n{state}\n",
                  file=sys.stderr, flush=True)

        return 0
    finally:
        try:
            browser.stop()
        except Exception:
            pass


def main() -> int:
    import nodriver as uc
    return uc.loop().run_until_complete(main_async())


if __name__ == "__main__":
    sys.exit(main())
