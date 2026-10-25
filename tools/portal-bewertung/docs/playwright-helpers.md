# Playwright-Helpers in `core/`

## Zweck

Portal-agnostische Bausteine für die Form-Automatisierung: Browser-Start,
Cookie-Banner-Dismiss, Input-Tipper, Radio-Klicker, Selects, Submit,
Result-Frame-Reader. Pro Funktion ein kurzer Abschnitt mit Signatur +
Beispielaufruf.

**Wichtig:** Diese Helpers sind nicht mit Unit-Tests abgedeckt
(DOM-Interaktion mockt sich schlecht). Die Verifikation läuft live
über die Portal-Migration in Step 7 (CHECK24) und Step 12–14 (Homeday,
Interhyp, IS24).

## Files

| Datei | Inhalt |
|---|---|
| [core/log.py](../core/log.py) | `log(msg)` + `set_verbose(bool)` — Logs auf stderr |
| [core/browser.py](../core/browser.py) | `launch_browser(playwright, cfg)` + `BrowserConfig` |
| [core/cookies.py](../core/cookies.py) | `dismiss_cookies(page, candidates, wrapper, max_wait_s, fallback_remove)` |
| [core/inputs.py](../core/inputs.py) | `input_typed`, `input_street_with_autocomplete`, `normalize_strasse_abbrev` |
| [core/radios.py](../core/radios.py) | `click_radio(page, qa_ref_sel, nudge_keys)`, `click_radio_by_label_text(page, label, nudge_keys)` |
| [core/selects.py](../core/selects.py) | `select_by_index`, `select_by_label` |
| [core/submit.py](../core/submit.py) | `wait_for_enabled_submit`, `click_submit` |
| [core/reader.py](../core/reader.py) | `find_result_frame`, `deep_scroll_frame`, `read_frame_body_deep`, `read_page_body_deep` |
| [core/modals.py](../core/modals.py) | `dismiss_modal_by_text(page, accept_texts)` — siehe [parsers.md](./parsers.md) |
| [tests/test_core_helpers_importable.py](../tests/test_core_helpers_importable.py) | 9 Smoke-Tests für Importierbarkeit + normalize-Test |

## `core/log.py`

```python
from core.log import log, set_verbose

set_verbose(True)
log("Bereit für Form-Befüllung.")  # → stderr
```

## `core/browser.py`

```python
from playwright.sync_api import sync_playwright
from core.browser import BrowserConfig, launch_browser

with sync_playwright() as p:
    browser, context, page = launch_browser(p, BrowserConfig(headless=True))
    page.goto("https://example.de")
    # ...
    context.close()
    browser.close()
```

## `core/cookies.py`

```python
from core.cookies import dismiss_cookies

dismiss_cookies(
    page,
    accept_candidates=['button:has-text("Akzeptieren")', 'button:has-text("OK")'],
    wrapper_selector=".c24-cookie-consent-wrapper",
    max_wait_s=12.0,
    fallback_remove_selectors=[".c24-strict-blocking-layer"],
)
```

## `core/inputs.py`

```python
from core.inputs import input_typed, input_street_with_autocomplete

input_typed(page, ".form-input", "45357", index=2)   # PLZ in das 3. Input
input_street_with_autocomplete(
    page, ".form-input", "Prosperstraße", index=3, normalize_abbrev=True
)
# → tippt "Prosperstr." und drückt Enter
```

## `core/radios.py`

```python
from core.radios import click_radio, click_radio_by_label_text

click_radio(page, 'input[qa-ref="kaufabsicht-kauf"]', nudge_keys=False)
click_radio_by_label_text(page, "1-3 Monate", nudge_keys=True)
```

Pfeil-Nudge (2× rechts, 2× links, Enter) ist nötig bei React-Forms, die
einen Tastatur-Event brauchen, um den Klick als `changed` zu registrieren
(z.B. CHECK24-Zeitrahmen-Radio).

## `core/selects.py`

```python
from core.selects import select_by_index, select_by_label

select_by_index(page, "select.form-select", index=0, option_label="Wohnung")
select_by_label(page, "#bathrooms", option_label="2")
```

## `core/submit.py`

```python
from core.submit import wait_for_enabled_submit, click_submit

if wait_for_enabled_submit(page, "button.submit", max_wait_s=60):
    click_submit(page, "button.submit")
```

## `core/reader.py`

```python
from core.reader import find_result_frame, deep_scroll_frame, read_frame_body_deep

frame = find_result_frame(page, marker_text="Marktwertermittlung")
if frame:
    deep_scroll_frame(frame, steps=20, step_delay_ms=250)
    body_text = read_frame_body_deep(frame)
```

`deep_scroll_frame` scrollt alle scrollbaren Container im Frame schrittweise
runter — PriceHubble + ähnliche lazy-loaden Inhalte.

## Bekannte Stolpersteine

- **Viewport muss groß genug sein** für Submit-Button (Default 1440×1600 in
  `BrowserConfig`). Bei zu kleinem Viewport: „Element outside viewport"-Fehler
  beim `click_submit`.
- **Cookie-Banner kann verzögert aufpoppen.** Der Helper pollt bis
  `max_wait_s` — daher die Schleife.
- **`input_street_with_autocomplete`** wartet 1.8 s zwischen Tippen und Enter
  (Default), damit Geo-Suggestion-Dropdown aufpoppen kann. Bei langsamen
  Portalen ggf. erhöhen.
- **Radio-Nudge** ist React-spezifisch — bei nativen HTML-Forms überflüssig
  und potentiell schädlich (würde Wert ändern). Daher `nudge_keys=False`
  als sicherer Default, wenn man unsicher ist.
- **`PlaywrightTimeoutError` Fallback:** Wenn `playwright` nicht importiert
  werden kann (z.B. in Pure-Logic-Tests), fällt `radios.py` auf `Exception`
  zurück. Im Live-Betrieb ist das nie ein Thema.
