# `core/portal_base.py` + `core/runner.py`

## Zweck

- **`PortalBase`** — abstrakte Basis-Klasse, von der alle Portal-Adapter
  (`Check24Portal`, `HomedayPortal`, ...) erben.
- **`run_with_page`** + **`run`** — generischer Runner, der für jedes Portal
  den gleichen Lebenszyklus durchläuft.
- **`RunConfig`** — Konfiguration für einen Lauf (Headless, Verbose, Browser).
- **`RunResult`** — Ergebnis-Container mit `.to_dict()` und `.to_json()`,
  matched das Output-Schema aus `DEVELOPMENT_GUIDELINES.md`.

## Files

- [core/portal_base.py](../core/portal_base.py)
- [core/runner.py](../core/runner.py)
- [tests/test_core_runner.py](../tests/test_core_runner.py) — 5 Tests mit
  FakePage + DummyPortal

## Lifecycle (`run_with_page`)

```
1. page.goto(portal.START_URL)
2. dismiss_cookies(...)              ← falls portal.COOKIE_ACCEPT_CANDIDATES gesetzt
3. portal.fill_form(page, d, cfg)    ← MUSS überschrieben werden
4. screenshot "after_fill"
5. wait_for_enabled_submit(...)
6. click_submit(...)
7. portal.dismiss_post_submit_modals(page)   ← optional, Default no-op
8. find_result_frame(page, portal.RESULT_FRAME_MARKER)
9. deep_scroll_frame(frame)
10. read_frame_body_deep(frame) → text
11. parse_marktwert_block(text), parse_trends(text)
12. portal.extract_dom_colors(page) → optional Trend-Farben-Override
13. trend_ampel(trends, dom_colors)
14. build_trend_label(...)
15. screenshot "result_ok" oder "result_empty"
16. RunResult zurückgeben
```

Jeder Schritt wird per Try/Except umfasst; bei Fehler:
`RunResult.status="error"`, `error_code="<step>_failed"`,
`error_message`, Screenshot wenn möglich.

## Mini-Tutorial: neues Portal implementieren

```python
# portals/<name>/portal.py
from typing import Any

from core.datensatz import GeneralisierterDatensatz
from core.inputs import input_typed, input_street_with_autocomplete
from core.modals import dismiss_modal_by_text
from core.portal_base import PortalBase, RunConfig
from core.selects import select_by_index

from . import selectors as sel


class MyPortal(PortalBase):
    NAME = "myportal"
    START_URL = "https://example.de/bewertung"
    COOKIE_ACCEPT_CANDIDATES = [
        'button:has-text("Alle akzeptieren")',
        'button:has-text("OK")',
    ]
    COOKIE_WRAPPER = "#cookie-banner"
    SUBMIT_SELECTOR = sel.SUBMIT_BUTTON
    RESULT_FRAME_MARKER = "Marktwertermittlung"

    def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
        select_by_index(page, sel.SELECT_TYP, 0, "Eigentumswohnung")
        input_typed(page, sel.INPUT_PLZ, d.plz)
        input_street_with_autocomplete(page, sel.INPUT_STRASSE, d.strasse)
        input_typed(page, sel.INPUT_HAUSNR, d.hausnr)
        # ... weitere Felder

    def dismiss_post_submit_modals(self, page: Any) -> None:
        dismiss_modal_by_text(page, ["später erinnern", "OK"])
```

Aufruf:

```python
from playwright.sync_api import sync_playwright
from core.runner import run
from core.portal_base import RunConfig

from portals.myportal.portal import MyPortal

result = run(MyPortal(), datensatz, RunConfig(headless=True, verbose=True))
print(result.to_json())
```

## `PortalBase` — Hooks

| Methode | Pflicht? | Default | Wofür |
|---|---|---|---|
| `fill_form(page, datensatz, cfg)` | **ja** | raises NotImplementedError | Form befüllen |
| `dismiss_post_submit_modals(page)` | nein | no-op | Topzinsen-/Cookie-/etc.-Modals nach Submit schließen |
| `extract_dom_colors(page)` | nein | `{}` | Portal-eigene Trend-Farben aus DOM lesen (Override für `trend_ampel`) |

## `RunResult` — Output-Schema

```json
{
  "status": "ok",
  "portal": "check24",
  "marktwert_eur_min": 168000,
  "marktwert_eur_max": 178000,
  "marktwert_eur_mittel": 173000,
  "trends": {"jahre_3": 6.7, "jahr_1": 3.0, "prognose": 1.4},
  "trend_ampel": "gruen",
  "trend_ampel_label": "steigend",
  "trend_label": "Marktwert 168.000 – 178.000 € (Mittel 173.000 €) Trend 🟢 steigend (+6.7% 3J / ...)",
  "url": "https://...",
  "timestamp": "2026-05-15T10:00:00+02:00",
  "screenshot_path": "runs/2026-05-15T100000_check24_result_ok.png",
  "raw_text_excerpt": "..."  // optional
}
```

Bei `status: "error"` zusätzlich `error_code`, `error_message`.

## Bekannte Limitierungen

- **`run_with_page` ruft kein `_ensure_cookies_dismissed` zweimal.** Falls
  ein Portal das Cookie-Banner nach Form-Befüllung wieder aufploppen lässt,
  muss der Adapter es in `fill_form` selbst handhaben (oder in
  `dismiss_post_submit_modals`).
- **Screenshots laufen mit `full_page=True`** — bei sehr langen Result-Seiten
  kann das langsam werden. Aktuell akzeptiert.
- **Keine Selektor-Recovery in dieser Phase.** Selektor-Fail → Error-JSON.
  LLM-Recovery kommt in Step 11.

## Tests

```bash
pytest tests/test_core_runner.py -v
```

5 Tests, alle mit FakePage + DummyPortal:
1. Reihenfolge der Portal-Hooks korrekt
2. Error bei nicht-gefundenem Result-Frame
3. Error bei Exception in `fill_form`
4. `PortalBase.fill_form` ist abstrakt
5. `RunResult.to_dict()` emittiert Schema-Felder
