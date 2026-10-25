"""Live-Exploration fuer Immometrica mit System-Chrome (Anti-Bot-Variante).

Nutzt Playwright's launch_persistent_context mit channel='chrome' (statt
Playwright-eigenem Chromium-Build) plus Anti-Detection-Flags, damit reCAPTCHA
den Browser NICHT als Bot erkennt. Cookies/Session werden im user_data_dir
unter learned_selectors/immometrica_userdata/ persistiert — nach einmaligem
Login kann das Skript kuenftig die existierende Session nutzen.

Stufe-1-Variante gegen reCAPTCHA-Block:
- channel='chrome' → System-Chrome (echter Browser-Fingerprint)
- --disable-blink-features=AutomationControlled → navigator.webdriver=false
- ignore_default_args=['--enable-automation'] → kein Test-Banner
- viewport=None → natives Fenster (kein device-emulation Mode)
- user_data_dir → persistente Cookies/History/Logins

Output:
    runs/<ts>_immometrica_explore_01_initial.png   (Initial-Screenshot)
    runs/<ts>_immometrica_explore_urls.log         (Navigations-Log)
    runs/<ts>_immometrica_explore_final_<n>.png    (Final-Screenshots pro Tab)
    runs/<ts>_immometrica_explore_state.json       (Storage-State, gitignored)
    learned_selectors/immometrica_userdata/        (Browser-User-Daten, gitignored)

Lauf:
    .venv\\Scripts\\python.exe inspectors/explore_immometrica.py
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

THIS_DIR = Path(__file__).resolve().parent
PROJ_ROOT = THIS_DIR.parent
RUNS_DIR = PROJ_ROOT / "runs"
STATE_DIR = PROJ_ROOT / "learned_selectors"
USER_DATA_DIR = STATE_DIR / "immometrica_userdata"
BERLIN_TZ = timezone(timedelta(hours=2))

# Stealth-Patches: werden vor jedem Page-Load injiziert. Ueberschreiben die
# typischen Bot-Marker, die reCAPTCHA prueft. Kein externes Lib noetig.
STEALTH_INIT_SCRIPT = r"""
// 1. navigator.webdriver -> undefined (manche Chrome-Versionen exposen es trotz Flag)
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. window.chrome Object mit realistischen Properties (Bots haben oft leeres chrome-Object)
if (!window.chrome) { window.chrome = {}; }
window.chrome.runtime = window.chrome.runtime || {};
window.chrome.loadTimes = window.chrome.loadTimes || function() { return {}; };
window.chrome.csi = window.chrome.csi || function() { return {}; };
window.chrome.app = window.chrome.app || { isInstalled: false };

// 3. navigator.permissions.query patchen (Bot-Detection-Pattern)
const _origQuery = window.navigator.permissions && window.navigator.permissions.query;
if (_origQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : _origQuery.call(window.navigator.permissions, parameters)
  );
}

// 4. navigator.plugins muss mindestens 3 enthalten (Bots haben oft leere plugins-Liste)
Object.defineProperty(navigator, 'plugins', {
  get: () => {
    const fake = [
      { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
      { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
      { name: 'Native Client', filename: 'internal-nacl-plugin' }
    ];
    fake.length = 3;
    return fake;
  }
});

// 5. navigator.languages realistisch
Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });

// 6. WebGL Vendor/Renderer ueberschreiben (SwiftShader = sofort verdaechtig)
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
  // UNMASKED_VENDOR_WEBGL
  if (parameter === 37445) { return 'Intel Inc.'; }
  // UNMASKED_RENDERER_WEBGL
  if (parameter === 37446) { return 'Intel Iris OpenGL Engine'; }
  return getParameter.call(this, parameter);
};

// 7. CDP-Detection (Console.debug-Side-Effect-Trick)
const _origDebug = console.debug;
console.debug = function() { return _origDebug.apply(console, arguments); };
"""


def _ts() -> str:
    return datetime.now(BERLIN_TZ).strftime("%Y-%m-%dT%H%M%S")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Live-Exploration fuer Immometrica mit System-Chrome (Anti-Bot)."
    )
    parser.add_argument(
        "--url", default="https://www.immometrica.com/de",
        help="Start-URL (Default: Marketing-Page)",
    )
    parser.add_argument(
        "--channel", default="chrome",
        help="Browser-Channel: chrome | msedge | chromium (Default: chrome)",
    )
    parser.add_argument(
        "--poll-interval-s", type=int, default=5,
        help="Wie oft URLs in Log geschrieben werden",
    )
    args = parser.parse_args(argv)

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    ts = _ts()
    log_path = RUNS_DIR / f"{ts}_immometrica_explore_urls.log"
    shot_initial = RUNS_DIR / f"{ts}_immometrica_explore_01_initial.png"
    state_path = RUNS_DIR / f"{ts}_immometrica_explore_state.json"

    from playwright.sync_api import sync_playwright

    print(f">>> Stufe-1-Variante: channel={args.channel!r}, persistent user_data_dir",
          file=sys.stderr, flush=True)
    print(f">>> user_data_dir: {USER_DATA_DIR}", file=sys.stderr, flush=True)
    print(f">>> Oeffne {args.url} (headed, Anti-Bot-Flags aktiv)",
          file=sys.stderr, flush=True)

    log_lines: list[str] = [
        f"=== Immometrica Exploration {ts} (Stufe-1, channel={args.channel}) ===\n",
    ]

    with sync_playwright() as pw:
        # Persistent Context = launch + context in einem.
        # channel='chrome' nutzt System-Chrome statt Playwright-Chromium.
        # ignore_default_args entfernt --enable-automation (sonst Test-Banner + Bot-Marker).
        # viewport=None => natives Fenster, kein device-emulation Mode.
        try:
            ctx = pw.chromium.launch_persistent_context(
                str(USER_DATA_DIR),
                channel=args.channel,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"],
                viewport=None,
                locale="de-DE",
                timezone_id="Europe/Berlin",
            )
        except Exception as e:
            print(f">>> FAIL: channel={args.channel!r} nicht startbar: {e}",
                  file=sys.stderr, flush=True)
            print(">>> Versuche Fallback channel='msedge'", file=sys.stderr, flush=True)
            try:
                ctx = pw.chromium.launch_persistent_context(
                    str(USER_DATA_DIR),
                    channel="msedge",
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport=None,
                    locale="de-DE",
                    timezone_id="Europe/Berlin",
                )
                print(">>> OK: msedge gestartet", file=sys.stderr, flush=True)
            except Exception as e2:
                print(f">>> FAIL auch msedge: {e2}", file=sys.stderr, flush=True)
                print(">>> Letzter Fallback: Playwright-Chromium (Bot-erkennbar!)",
                      file=sys.stderr, flush=True)
                ctx = pw.chromium.launch_persistent_context(
                    str(USER_DATA_DIR),
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"],
                    viewport=None,
                    locale="de-DE",
                    timezone_id="Europe/Berlin",
                )

        # Stealth-Patches in den Context injizieren — werden vor jeder
        # Page-Navigation ausgefuehrt. Ueberschreiben Bot-Marker.
        try:
            ctx.add_init_script(STEALTH_INIT_SCRIPT)
            print(">>> Stealth-Init-Script injiziert", file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Stealth-Init-Script FAIL: {e}",
                  file=sys.stderr, flush=True)

        # Falls Persistent-Context schon eine Default-Page hat, diese nutzen.
        pages = list(ctx.pages)
        if pages:
            page = pages[0]
        else:
            page = ctx.new_page()

        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(3_000)
        try:
            page.screenshot(path=str(shot_initial), full_page=False)
            print(f">>> Initial-Screenshot: {shot_initial.name}",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Screenshot FAIL: {e}", file=sys.stderr, flush=True)

        last_urls: dict[int, str] = {}
        log_lines.append(f"[{_ts()}] Tab0 initial: {page.url}\n")
        log_path.write_text("".join(log_lines), encoding="utf-8")

        print(
            f">>> Polle alle {args.poll_interval_s}s die offenen Tab-URLs.",
            file=sys.stderr, flush=True,
        )
        print(
            ">>> Klicke dich durch: Cookies/Newsletter weg, 'Anmelden', Login.",
            file=sys.stderr, flush=True,
        )
        print(
            ">>> reCAPTCHA sollte jetzt laden (falls Box: einmal anklicken).",
            file=sys.stderr, flush=True,
        )
        print(
            ">>> Wenn im Dashboard/Search: Browser-Fenster schliessen.",
            file=sys.stderr, flush=True,
        )

        try:
            while True:
                pages = list(ctx.pages)
                if not pages:
                    print(">>> Alle Tabs zu — beende.", file=sys.stderr, flush=True)
                    break
                changed = False
                for i, p in enumerate(pages):
                    try:
                        if p.is_closed():
                            continue
                        u = p.url
                    except Exception:
                        continue
                    if last_urls.get(i) != u:
                        log_lines.append(f"[{_ts()}] Tab{i}: {u}\n")
                        last_urls[i] = u
                        changed = True
                if changed:
                    log_path.write_text("".join(log_lines), encoding="utf-8")
                time.sleep(args.poll_interval_s)
        except KeyboardInterrupt:
            print(">>> KeyboardInterrupt — speichere State und beende.",
                  file=sys.stderr, flush=True)
        except Exception as e:
            print(f">>> Poll-Loop Exception: {e}", file=sys.stderr, flush=True)

        # Final-Screenshots aller noch offenen Tabs
        try:
            for i, p in enumerate(list(ctx.pages)):
                try:
                    if p.is_closed():
                        continue
                    final_shot = RUNS_DIR / f"{ts}_immometrica_explore_final_{i}.png"
                    p.screenshot(path=str(final_shot), full_page=False)
                    print(f">>> Final-Screenshot Tab{i}: {final_shot.name} ({p.url})",
                          file=sys.stderr, flush=True)
                    log_lines.append(f"[{_ts()}] FINAL Tab{i}: {p.url}\n")
                except Exception:
                    continue
        except Exception:
            pass

        # Storage-State als zusaetzliche Sicherung (user_data_dir reicht eigentlich)
        try:
            ctx.storage_state(path=str(state_path))
            size = state_path.stat().st_size
            print(f">>> Storage-State gespeichert: {state_path.name} ({size} bytes)",
                  file=sys.stderr, flush=True)
            log_lines.append(f"[{_ts()}] STATE saved: {state_path.name} ({size} bytes)\n")
        except Exception as e:
            print(f">>> Storage-State FAIL: {e}", file=sys.stderr, flush=True)
            log_lines.append(f"[{_ts()}] STATE FAIL: {e}\n")

        try:
            log_path.write_text("".join(log_lines), encoding="utf-8")
        except Exception:
            pass

        try:
            ctx.close()
        except Exception:
            pass

    print(">>> Fertig.", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
