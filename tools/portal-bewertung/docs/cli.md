# CLI-Entry: `m00_portal_pricer.py`

## Zweck

Zentraler Einstiegspunkt für Portal-Bewertungen. Dispatcht auf den
gewünschten Portal-Adapter, gibt strukturiertes JSON auf stdout aus.

## Files

- [m00_portal_pricer.py](../m00_portal_pricer.py)
- [tests/test_cli_importable.py](../tests/test_cli_importable.py) — 6 Tests

## Pflicht-Argument

| Argument | Werte | Beschreibung |
|---|---|---|
| `--portal` | `check24` | Welches Portal — weitere kommen in Steps 12–14 |

## Datensatz-Quelle (eines davon)

**Mode A: JSON-Datei (für Cloud-Integration / Modul 0):**

```bash
python m00_portal_pricer.py --portal check24 --datensatz runs/datensatz.json
```

Die JSON-Datei muss den `GeneralisierterDatensatz` als Dict abbilden:

```json
{
  "strasse": "Prosperstr.",
  "hausnr": "59",
  "plz": "45357",
  "ort": "Essen",
  "baujahr": 1965,
  "zustand": "gut",
  "ausstattung": "normal",
  "anzahl_we": 4,
  "avg_wohnflaeche_qm": 80,
  "avg_zimmer": 3,
  "avg_badezimmer": 1,
  "hat_garage": false,
  "hat_aussenstellplatz": false
}
```

**Mode B: CLI-Args (für manuellen Aufruf):**

```bash
python m00_portal_pricer.py --portal check24 \
  --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen \
  --baujahr 1965 --zustand gut --ausstattung normal \
  --anzahl-we 4 --gesamtwohnflaeche-qm 320 --gesamtzimmer 12
```

Oder mit WE-Einzel-Listen:

```bash
python m00_portal_pricer.py --portal check24 \
  --strasse "Prosperstraße" --hausnr 59 --plz 45357 --ort Essen \
  --baujahr 1965 --zustand gut --ausstattung normal \
  --anzahl-we 4 \
  --wohnflaechen-qm "60,70,80,90" \
  --zimmer-liste "2,3,3,4" \
  --badezimmer-liste "1,1,1,2"
```

## Run-Flags

| Flag | Default | Beschreibung |
|---|---|---|
| `--kaufabsicht` | `kauf` | `kauf` oder `verkauf` (CHECK24 hat Radios dafür) |
| `--headless` | aus | Browser im Hintergrund (kein UI-Fenster) |
| `--verbose` | aus | Diagnose-Logs auf **stderr** (stdout bleibt für JSON reserviert) |

## Output-Schema

stdout (UTF-8) enthält das JSON aus `RunResult.to_dict()` + zusätzlich
`generalisierter_datensatz` (für Audit-Trail):

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
  "trend_label": "Marktwert 168.000 – 178.000 € (Mittel 173.000 €) ...",
  "url": "https://...",
  "timestamp": "2026-05-15T10:00:00+02:00",
  "screenshot_path": "runs/2026-05-15T100000_check24_result_ok.png",
  "generalisierter_datensatz": { ... }
}
```

Bei `status: "error"` zusätzlich `error_code` + `error_message`.

## Exit-Codes

- `0` — `status == "ok"`
- `1` — `status == "error"` ODER Argument-Validation-Failure
  (`SystemExit` aus argparse)

## Beispielaufruf (PowerShell, Windows)

```powershell
cd c:\meine-projekte\Immobilien\Aufteiler\tools\portal-bewertung
.\.venv\Scripts\python.exe m00_portal_pricer.py `
  --portal check24 `
  --strasse "Prosperstraße" `
  --hausnr 59 `
  --plz 45357 `
  --ort Essen `
  --baujahr 1965 `
  --zustand gut `
  --ausstattung normal `
  --anzahl-we 4 `
  --gesamtwohnflaeche-qm 320 `
  --gesamtzimmer 12 `
  --headless `
  --verbose
```

## Bekannte Limitierungen

- **`--datensatz`-JSON erwartet bereits berechnete Durchschnittswerte**
  (`avg_wohnflaeche_qm`, `avg_zimmer`). Die `from_summary`/`from_lists`-
  Factories sind nicht erreichbar über JSON-Eingabe.
- **Windows UTF-8:** stdout wird per `sys.stdout.reconfigure(encoding="utf-8")`
  auf UTF-8 umgestellt — sonst kotzt Windows-CP1252 bei deutschen Umlauten +
  Emojis im `trend_label`.
- **Keine Live-Lauf-Verifikation in dieser Session.** Akzeptanzkriterium aus
  Step 8 ("Live-Lauf durch") wurde nicht automatisiert — der User muss den
  Lauf gegen die echte CHECK24-Site auslösen.
