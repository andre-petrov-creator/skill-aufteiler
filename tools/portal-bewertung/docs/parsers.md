# `core/parsers.py` + `core/modals.py`

## Zweck

Portal-agnostische Bausteine:

- **`core/parsers.py`** — Regex-Parser für Marktwert-Block, Trends und
  Ampel-Logik. Operiert auf reinem Text (`frame.inner_text()`-Output).
- **`core/modals.py`** — generischer Modal-Dismisser via `:has-text()`-Selector.
  Wird für Cookie-Banner + Post-Submit-Overlays genutzt.

Beides ist portal-frei: keine `if portal == "check24"`-Logik, keine
hartcodierten Portal-Namen.

## Files

- [core/parsers.py](../core/parsers.py)
- [core/modals.py](../core/modals.py)
- [tests/test_core_parsers.py](../tests/test_core_parsers.py) — 14 Tests
- [tests/test_core_modals.py](../tests/test_core_modals.py) — 4 Tests

## `parsers.py` — Schnittstellen

### `parse_marktwert_block(text) -> {min, max, mittel}`

Sucht nach diesen Patterns im Text:
- `Marktwert ... <Zahl> €` → `mittel`
- `Marktwertspanne ... <Zahl> - <Zahl> €` → `min` / `max`

Trennzeichen zwischen Label und Zahl: Newlines, Pipes, Spaces — alles wird
erfasst. Bei fehlenden Werten: `None`.

### `parse_trends(text) -> {jahre_3, jahr_1, prognose}`

Sucht die drei Trend-Labels:
- `In den letzten 3 Jahren` (oder `letzten 3 Jahren`) → `jahre_3`
- `Seit letztem Jahr` → `jahr_1`
- `Prognose für das nächste Jahr` (Umlaut tolerant) → `prognose`

Pro Label wird *rückwärts* der letzte Prozent-Wert davor genommen. Vorzeichen
(`+`/`-`) und Komma-Dezimaltrennzeichen werden erfasst.

### `trend_ampel(trends, dom_colors=None) -> (ampel, label)`

Heuristik-Schwellen (eigene):

| Bedingung | Ampel |
|---|---|
| `prognose < 0` | rot („fallend (Prognose negativ)") |
| `jahr_1 < 0 AND jahre_3 < 0` | rot („fallend (1-J + 3-J negativ)") |
| `|3J| < 2% AND |1J| < 1.5%` ODER `prognose ≤ 1%` | gelb („stagnierend") |
| sonst | grün („steigend") |

**Override per `dom_colors`:** Wenn ein Portal eigene Farb-Hinweise im DOM
liefert (z.B. CSS-Klassen `green`/`red`), übergibt der Portal-Adapter ein
`{jahre_3: "gruen", jahr_1: "rot", ...}`-Dict. Der Mehrheitsentscheid
überschreibt die Heuristik (Label-Suffix: „(Portal-DOM)").

### `build_trend_label(*, marktwert, trends, ampel, ampel_label) -> str`

Baut eine menschenlesbare Zusammenfassung:

```
Marktwert 168.000 – 178.000 € (Mittel 173.000 €) Trend 🟢 steigend (+6.7% 3J / +3.0% 1J / +1.4% Prognose)
```

**Wichtig:** **kein Portal-Prefix** im Label. Der Portal-Name kommt im
Output-JSON separat als `portal`-Feld; Konsumenten (Modul 5 PDF, Modul 0)
kombinieren beide nach eigenem Layout.

Emojis (🟢🟡🔴) werden eingebettet — Konsumenten, die Emoji-frei rendern
müssen (z.B. reportlab-PDF ohne passende Unicode-Schrift), parsen das
Label oder generieren den String aus den Rohdaten neu.

## `modals.py` — Schnittstelle

```python
dismiss_modal_by_text(
    page,
    accept_texts: list[str],
    *,
    click_timeout_ms: int = 3_000,
    settle_ms: int = 400,
) -> bool
```

Probiert für jeden Text in der Liste den Selector `button:has-text("<text>")`
durch, klickt den ersten **sichtbaren** Match (`is_visible() == True`).
Liefert `True` wenn geklickt, sonst `False`.

Beispiel-Aufruf aus einem Portal-Adapter:

```python
dismiss_modal_by_text(page, ["später erinnern", "Später erinnern", "Schließen"])
```

Page-Typ ist als `Protocol` deklariert — der Helper braucht nur
`page.locator()` + `page.wait_for_timeout()`, also läuft er sowohl gegen
echtes `playwright.Page` als auch gegen unsere Test-Mocks.

## Bekannte Limitierungen

- **Marktwert-Regex erwartet deutsches Tausender-Format (`168.000`).**
  Portale mit englischem Format (`168,000`) brauchen Anpassung.
- **Trend-Labels sind deutsch.** Englische Portale (sehr unwahrscheinlich
  für unseren Use-Case) bräuchten zusätzliche Label-Patterns.
- **`build_trend_label` benutzt Unicode-Emojis.** Konsumenten ohne Unicode-
  Support müssen die Emojis selbst rausfiltern oder das Label aus Rohdaten
  neu bauen.
- **`dismiss_modal_by_text` macht Substring-Match** (Playwright-Default für
  `:has-text()`). Für exakte Matches müsste der Aufrufer `text="..."`
  manuell setzen.

## Tests

```bash
pytest tests/test_core_parsers.py tests/test_core_modals.py -v
```

18 Tests, 0.1 s, alle grün. Decken ab:
- Marktwert-Format mit Newlines / Pipes / leer
- Trends 3-fach / mit Negative / mit fehlendem Label
- Ampel grün / gelb / rot (zwei Pfade) / DOM-Override
- Trend-Label mit/ohne Prognose / kein Portal-Prefix
- Modal-Dismisser klickt ersten sichtbaren / skippt unsichtbare /
  leere Liste returnt False
