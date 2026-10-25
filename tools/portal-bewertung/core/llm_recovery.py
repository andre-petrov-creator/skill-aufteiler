"""LLM-Recovery für gebrochene Selektoren via Anthropic-API.

Bei DOM-Änderung eines Portals wird Claude mit DOM-Dump + Screenshot
gefragt, einen neuen Selektor zu liefern. Wird VOR der Persistierung
gegen die echte Page getestet — invalid → None.

Konfiguration via Umgebungsvariable `ANTHROPIC_API_KEY` (in `.env`).
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from core.log import log

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_DOM_CHARS = 30_000  # Cap auf DOM-Snapshot, sonst sprengt's das Prompt-Limit


def get_client() -> Optional[Any]:
    """Liefert einen Anthropic-Client, wenn API-Key gesetzt. Sonst None."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from anthropic import Anthropic

        return Anthropic(api_key=api_key)
    except ImportError:
        log("anthropic-SDK nicht installiert — Recovery deaktiviert.")
        return None


def _build_prompt(
    *,
    portal_name: str,
    intent: str,
    failed_selector: str,
    dom_snippet: str,
) -> str:
    return f"""Du hilfst beim Reparieren eines gebrochenen CSS-Selektors auf der \
Bewertungsseite des Portals "{portal_name}".

Intent (was der Selektor finden soll): {intent}
Gebrochener Selektor: {failed_selector!r}

Liefere als Antwort EINEN neuen CSS-Selektor (ohne Erklärung, ohne Anführungszeichen, \
kein Markdown-Codeblock), der das gleiche Element findet. Bevorzuge stabile \
Attribute (`data-*`, `aria-*`, `qa-ref`, `id`) gegenüber Klassen-Namen.

Falls du nichts Passendes findest: Antworte mit dem String "NONE".

DOM-Ausschnitt (gekappt):
```html
{dom_snippet[:MAX_DOM_CHARS]}
```
"""


def _strip_response(text: str) -> str:
    """Holt einen rohen Selektor aus der LLM-Antwort.

    LLM gibt manchmal Markdown-Code-Fences oder Anführungszeichen zurück —
    räumen wir auf.
    """
    out = text.strip()
    # Markdown-Codefence raus
    fence = re.search(r"```(?:[a-zA-Z]*\n)?(.*?)```", out, re.DOTALL)
    if fence:
        out = fence.group(1).strip()
    out = out.strip("`")
    out = out.strip().strip('"').strip("'")
    return out


def _test_selector(page: Any, selector: str) -> bool:
    """Prüft ob ein Selektor auf der Page ein sichtbares Element findet."""
    try:
        loc = page.locator(selector).first
        return loc.count() > 0 and loc.is_visible()
    except Exception:
        return False


def _dump_dom(page: Any, max_chars: int = MAX_DOM_CHARS) -> str:
    """Holt das HTML als String, gekappt."""
    try:
        html = page.evaluate("() => document.documentElement.outerHTML")
        return (html or "")[:max_chars]
    except Exception:
        return ""


def recover_selector(
    page: Any,
    *,
    failed_selector: str,
    intent: str,
    portal_name: str,
    client: Optional[Any] = None,
    model: str = DEFAULT_MODEL,
) -> Optional[str]:
    """Versucht einen neuen Selektor via LLM zu finden und zu validieren.

    Returns: der neue Selektor, wenn auf der Page sichtbar — sonst None.
    Der Aufrufer entscheidet selbst, ob er ihn persistiert
    (`core.selectors_store.save_learned_selector`).
    """
    if client is None:
        client = get_client()
    if client is None:
        log("Kein Anthropic-Client (API-Key fehlt) — Recovery übersprungen.")
        return None

    dom_snippet = _dump_dom(page)
    prompt = _build_prompt(
        portal_name=portal_name,
        intent=intent,
        failed_selector=failed_selector,
        dom_snippet=dom_snippet,
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        log(f"Recovery-API-Aufruf fehlgeschlagen: {e}")
        return None

    raw_text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw_text += getattr(block, "text", "")
    if not raw_text:
        return None

    candidate = _strip_response(raw_text)
    if not candidate or candidate.upper() == "NONE":
        return None

    if not _test_selector(page, candidate):
        log(f"LLM lieferte Selektor {candidate!r}, matched aber nichts — verworfen.")
        return None

    log(f"LLM-Recovery für {portal_name}.{intent}: {candidate!r}")
    return candidate
