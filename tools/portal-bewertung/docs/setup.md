# Setup: Portal-Bewertung

**Zweck:** Reproduzierbare lokale Python-Umgebung für das Portal-Bewertungs-Tool aufsetzen.

## Voraussetzungen

- **Python 3.13+** (3.14 wird genutzt, 3.13 reicht). Prüfen: `python --version`
- **Windows PowerShell** (wird für Aktivierung der venv genutzt)
- **Anthropic API-Key** (nur ab Step 11 nötig — für LLM-Selektor-Recovery)

## Setup-Reihenfolge

```powershell
# 1. In Projekt-Ordner wechseln
cd C:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung

# 2. venv anlegen
python -m venv .venv

# 3. venv aktivieren
.\.venv\Scripts\Activate.ps1

# 4. Python-Dependencies installieren
pip install -r requirements.txt

# 5. Chromium für Playwright installieren (~150 MB Download)
playwright install chromium

# 6. Smoke-Test
pytest
```

## Files

| Datei | Zweck |
|---|---|
| `requirements.txt` | Python-Dependencies (playwright, pytest, anthropic, python-dotenv) |
| `pytest.ini` | Pytest-Config: `slow`-Marker für Live-Tests, default `-m "not slow"` |
| `tests/__init__.py` | Macht `tests/` zum importierbaren Package |
| `tests/test_smoke.py` | Mini-Test, beweist dass venv + pytest funktionieren |
| `.venv/` | Lokale venv (gitignored) |
| `.env` | `ANTHROPIC_API_KEY=...` (gitignored, optional bis Step 11) |

## Verifizierte Versionen (Stand 2026-05-15)

| Komponente | Version |
|---|---|
| Python | 3.14.3 |
| pip | 26.1.1 |
| playwright | 1.59.0 |
| pytest | 9.0.3 |
| anthropic | 0.102.0 |
| python-dotenv | 1.2.2 |
| Chromium (über Playwright) | 147.0.7727.15 |

## Bekannte Limitierungen

- **`.venv/` ist nicht teilbar** zwischen Windows und WSL — bei OS-Wechsel neu anlegen.
- **`playwright install chromium`** lädt jedes Mal die volle Chromium-Version, kein inkrementelles Update. Eine zweite Installation in eine bestehende venv ist trotzdem schnell (Cache wird genutzt).
- **Anthropic-Key ist optional** bis Step 11 (LLM-Recovery). Vorher kein Key nötig.

## Test-Ausführung

```powershell
# Default — nur Unit-Tests
pytest

# Inklusive Live-Tests gegen echte Portale (manuell!)
pytest -m "" -v

# Nur ein bestimmtes Modul
pytest tests/test_core_parsers.py -v
```
