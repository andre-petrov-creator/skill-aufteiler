# Step 14 — Stand 2026-05-19 (Phase 2 fertig)

## TL;DR

Step 14 (Immometrica-Adapter) **Phase 2 abgeschlossen**. Adapter laeuft
**vollautonom**: Login, Sidebar-Navigation, 6 Configs mit Geo/Period/Radio/
MFH/Baujahr-Filter, Submit, Body-Stats-Parsing + Chart.js-Datenextraktion.
Live-Test mit Prosperstr. 59 (45357 Essen, BJ 1965) durchgelaufen, alle
6 Configs status=ok.

## Live-Test-Ergebnis 2026-05-19T20:08

```
Config plz_etw         (PLZ + ETW + MFH off):         Anz=45    Preis=2200 €/m²  Rendite=5.1%
Config plz_mietwohnung (PLZ + Mietwohnung + MFH off): Anz=89    Preis=9.27 €/m²
Config plz_mfh         (PLZ + Hauskauf + MFH on):     Anz=8     Preis=1204 €/m²  Rendite=9.2%
Config stadt_etw       (Stadt + ETW + MFH off):       Anz=291   Preis=1765 €/m²  Rendite=6.3%
Config stadt_mietwohn. (Stadt + Mietwohnung):         Anz=935   Preis=2333 €/m²
Config stadt_mfh       (Stadt + Hauskauf + MFH on):   Anz=3166  Preis=9.2  €/m²

Status final: ok
```

Plus pro Config 18 Chart.js-Datenpunkte (Verteilungen nach Zimmer / Wohnflaeche
/ Baujahr × Angebote / Kaufpreis / Online-Dauer).

## Architektur (siehe Memories)

| Memory | Inhalt |
|---|---|
| [[immometrica-marktstatistik-workflow]] | 28-Klick-Sequenz, 6 Configs, Sidebar-Klick, Geo-vor-Period, Enter via CDP |
| [[immometrica-baujahr-filter]] | Range 1900 bis max(1980, BJ+5), Input-IDs `id_construction_year_0/1` |
| [[immometrica-9-tabellen]] | 18 Chart.js-Charts, 2 Gruppen × 3 Dim × 3 Metriken, Extraktion via `Chart.instances` |
| [[user-workflow-erfragen-statt-raten]] | Bei UI-Adapter-Fail erst User-Workflow erfragen |

## Wichtige Helper-Funktionen im Adapter

- `_click_marktstatistik_sidebar(tab)` — Sidebar-Link statt direkter URL
- `_wait_for_marktstatistik_ready(tab, timeout_s=20)` — Polling auf Form-Marker
- `_enter_geo(tab, geo, expected)` — Tippen + Enter via CDP
- `_press_enter(tab)` — echter Enter-Keystroke via `cdp.input_.dispatch_key_event`
- `_set_baujahr_range(tab, von, bis)` — Native-Setter auf `id_construction_year_0/1` + Polling
- `_calc_baujahr_bis(baujahr) -> int` — `max(1980, baujahr+5)`
- `_get_chart_data(tab)` — extrahiert 18 Chart.js-Datasets, strukturiert nach Dimension/Metrik
- `_wait_for_stat_loaded(tab, timeout_s=90)` — Polling auf "Übersicht:" + ohne "Wird geladen…"

## Wichtige Architektur-Regeln

- **KEIN `tab.get` zwischen Configs** — IntercoolerJS-Server-State bleibt sticky
- **Geo IMMER vor Period** — Period-Klick zerbricht React-Select
- **Geo nur 2× pro Lauf setzen** (PLZ + Stadt) — danach sticky
- **`send_keys("Enter")` NICHT** — schickt 5 char-Events, kein Keystroke. Stattdessen `_press_enter`
- **Submit-Server-Response variabel** — 15-60+ Sekunden, daher 90s Timeout

## Files

```
portals/immometrica/portal.py   — Adapter (Phase 2)
portals/immometrica/parsers.py  — parse_stat_block (Übersicht + Zusatzinfo aus body.innerText)
docs/portal-immometrica.md      — Phase-2-Doku
inspectors/diagnose_9_tabellen.py — Diagnose-Tool fuer DOM + Chart-Dumps
inspectors/test_immometrica_adapter.py — Live-Smoke-Test, jetzt mit baujahr=1965
inspectors/login_immometrica_autonomous.py — Cookie-Refresh bei Session-Ablauf
inspectors/training_immometrica.py — Network-Sniff (Dev-Tool, optional)
inspectors/probe_geo_input.py    — isolierte Geo-Probe (Dev-Tool, kept fuer Reference)
inspectors/probe_baujahr_inputs.py — Baujahr-Inputs-Probe (Dev-Tool)
inspectors/probe_location_api.py  — Location-API-Probe (Dev-Tool)
```

## Commits (Phase 2, heute)

In Arbeit. Final-Commit nach diesem Status-Update.

## Naechste Steps

1. Commit + Push auf main (Phase 2 dieses Adapter abgeschlossen)
2. Step 15: Orchestrator + `--alle`-Mode (alle 4 Portale parallel)
