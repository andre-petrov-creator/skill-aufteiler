"""Test-Skript: was gibt /de/api/location?q=45357 zurueck?"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
USER_DATA_DIR = PROJ_ROOT / "learned_selectors" / "immometrica_nodriver_userdata"


async def main_async() -> int:
    import nodriver as uc

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
        tab = await browser.get("https://www.immometrica.com/de/statistics")
        await asyncio.sleep(3.0)

        for q in ["45357", "Essen", "essen"]:
            print(f"\n=== Query: {q!r} ===")
            # Variante 1: await_promise=True
            try:
                r = await tab.evaluate(
                    f"""(async () => {{
                        const resp = await fetch(
                            '/de/api/location?q=' + encodeURIComponent({json.dumps(q)}),
                            {{credentials: 'include'}}
                        );
                        const txt = await resp.text();
                        return JSON.stringify({{status: resp.status, body: txt}});
                    }})()""",
                    await_promise=True,
                )
                if isinstance(r, dict) and "value" in r:
                    r = r["value"]
                print(f"  await_promise=True: {str(r)[:500]}")
            except Exception as e:
                print(f"  await_promise=True FAIL: {e}")

            # Variante 2: ohne await_promise (default)
            try:
                r2 = await tab.evaluate(
                    f"""(async () => {{
                        const resp = await fetch(
                            '/de/api/location?q=' + encodeURIComponent({json.dumps(q)}),
                            {{credentials: 'include'}}
                        );
                        const txt = await resp.text();
                        return JSON.stringify({{status: resp.status, body: txt}});
                    }})()""",
                )
                if isinstance(r2, dict) and "value" in r2:
                    r2 = r2["value"]
                print(f"  default: {str(r2)[:500]}")
            except Exception as e:
                print(f"  default FAIL: {e}")
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
