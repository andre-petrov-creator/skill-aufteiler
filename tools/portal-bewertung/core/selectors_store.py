"""Persistenz für LLM-gelernte Selektoren — JSON pro Portal.

Format: `learned_selectors/<portal>.json` mit `{intent: selector}`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

DEFAULT_BASE_DIR = Path(__file__).resolve().parent.parent / "learned_selectors"


def _store_path(portal_name: str, base_dir: Optional[Path] = None) -> Path:
    base = base_dir or DEFAULT_BASE_DIR
    return base / f"{portal_name}.json"


def load_learned_selectors(
    portal_name: str, *, base_dir: Optional[Path] = None
) -> dict[str, str]:
    """Liest gelernte Selektoren für ein Portal. Fehlende Datei → leeres Dict."""
    path = _store_path(portal_name, base_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_learned_selector(
    portal_name: str,
    intent: str,
    selector: str,
    *,
    base_dir: Optional[Path] = None,
) -> None:
    """Persistiert einen gelernten Selektor unter `<portal>.json[intent]`."""
    if not portal_name:
        raise ValueError("portal_name darf nicht leer sein")
    if not intent:
        raise ValueError("intent darf nicht leer sein")
    if not selector:
        raise ValueError("selector darf nicht leer sein")

    existing = load_learned_selectors(portal_name, base_dir=base_dir)
    existing[intent] = selector

    path = _store_path(portal_name, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
