# LLM-Recovery + Selectors-Store

## Zweck

Wenn ein Portal seine DOM-Struktur ändert (Klassen umbenannt, IDs entfernt),
bricht der hartcodierte Selektor. Statt sofort einen Error-JSON zu liefern,
fragt das Tool dann Claude (Anthropic-API) mit DOM-Dump + Intent und
bekommt einen neuen Selektor zurück. Der wird **vor** der Persistierung
gegen die echte Seite getestet — invalid → verworfen.

Gelernte Selektoren werden pro Portal in
`learned_selectors/<portal>.json` persistiert und beim nächsten Lauf
geladen.

## Files

- [core/llm_recovery.py](../core/llm_recovery.py) — `recover_selector()` + Helpers
- [core/selectors_store.py](../core/selectors_store.py) — `load_learned_selectors`, `save_learned_selector`
- [tests/test_core_llm_recovery.py](../tests/test_core_llm_recovery.py) — 4 Tests, mocked Anthropic-Client
- [tests/test_core_selectors_store.py](../tests/test_core_selectors_store.py) — 6 Tests
- [.env.example](../.env.example) — `ANTHROPIC_API_KEY=` Vorlage
- `learned_selectors/<portal>.json` — gelernte Selektoren (gitignored)

## Schnittstellen

### `recover_selector(page, failed_selector, intent, portal_name, client=None) -> str | None`

Hauptfunktion. `client=None` → liest API-Key aus `ANTHROPIC_API_KEY`-Env-Var.

Ablauf:

1. DOM dumpen (`document.documentElement.outerHTML`, max 30k chars)
2. Prompt bauen mit `intent`, `failed_selector`, Portal-Name, DOM-Snippet
3. Claude Sonnet 4.6 fragen — Antwort soll **nur** der Selektor sein, oder `NONE`
4. Antwort cleanen (Markdown-Codefence + Quotes raus)
5. Kandidat-Selektor gegen Page testen — `count() > 0 && is_visible()`
6. Bei Erfolg: Selektor zurückgeben. Aufrufer entscheidet, ob er ihn speichert.

### `save_learned_selector(portal, intent, selector)` / `load_learned_selectors(portal)`

JSON-Persistenz. `intent` ist ein logischer Name wie `cookie_accept`,
`plz_input`, `submit_button` — nicht der gebrochene Selektor selbst, damit
Updates über die Zeit funktionieren.

## Beispiel-Integration (manuell, nicht im Runner automatisiert)

```python
from core.llm_recovery import recover_selector
from core.selectors_store import (
    load_learned_selectors,
    save_learned_selector,
)

learned = load_learned_selectors("check24")

# Erst gelernten Selektor probieren, dann hartcodierten
def select_with_recovery(page, intent, hardcoded):
    candidate = learned.get(intent, hardcoded)
    if page.locator(candidate).first.count() > 0:
        return candidate
    new_sel = recover_selector(
        page, failed_selector=candidate, intent=intent, portal_name="check24"
    )
    if new_sel:
        save_learned_selector("check24", intent, new_sel)
        return new_sel
    raise RuntimeError(f"Selector recovery failed for {intent}")
```

## Kosten + Risiken

- **Recovery-Aufruf:** ein Claude-Sonnet-Call mit ~5–30k Input-Tokens
  (DOM-Dump) + ~50 Output-Tokens. **Ca. 0,05–0,30 € pro Aufruf**.
- **Erst nach Persistierung kostenlos:** Beim 2. Lauf wird der gelernte
  Selektor direkt genutzt, kein API-Call.
- **Wenn LLM eine invalid CSS-Syntax liefert:** `page.locator()` würfe
  intern, `_test_selector` fängt das ab → `None`.
- **Wenn LLM einen passenden Selektor liefert, der etwas Anderes findet
  als gewollt:** Nur das Live-Verhalten zeigt das. Recovery testet nur
  „Element existiert + sichtbar", nicht „macht das Richtige". Daher
  weiterhin manueller Live-Check nach jedem Recovery sinnvoll.

## Bekannte Limitierungen

- **Keine Auto-Integration im Runner.** Aktuell sind `recover_selector` +
  `selectors_store` Standalone-Bausteine. Ein Selektor-Fail in
  `core/runner.py` liefert ein Error-JSON, statt automatisch Recovery zu
  triggern. Der Hook müsste in jeden Helper (`input_typed`, `click_radio`,
  ...) eingebaut werden — bewusst noch nicht gemacht, weil das viele
  Stellen anfasst und die Recovery-Pfad-Komplexität ohne Notfall noch
  nicht gerechtfertigt ist. **Wenn ein DOM-Bruch auftritt: Recovery
  manuell von außen aufrufen, Selektor speichern, Portal-Adapter
  patchen.**
- **Manuelle Bruchprobe noch nicht durchgeführt.** Akzeptanzkriterium des
  Plans (künstlich falscher Cookie-Selektor → Recovery lernt richtigen)
  ist Code-vorbereitet, aber nicht durchgespielt. Erfordert API-Key in
  `.env` + manuellen Lauf.
- **`anthropic`-SDK importiert lazy.** Falls SDK fehlt: Recovery liefert
  `None`. Tests laufen ohne SDK durch (Client wird gemockt).

## Tests

```bash
pytest tests/test_core_llm_recovery.py tests/test_core_selectors_store.py -v
```

10 Tests, alle grün:

- Store: load missing → empty, save+load roundtrip, multiple intents,
  overwrite, validation (empty portal/selector)
- Recovery: mocked client returns selector / candidate fails / no client /
  strip codefence+quotes
