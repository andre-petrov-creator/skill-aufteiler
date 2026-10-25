---
name: aufteiler-marktdaten-fallback
description: Sub-Skill für Modul 1 (GMB-Lookup, Auto-Analyse) und Modul 5 (Mietspiegel-Lookup, Miete) — Auto-Fallback bei Notion-DB-Lookup-Fail. Quellen-Kaskade nur offiziell (Notion → BORIS NRW / Stadt-Webseite / Geoportal NRW → site-restricted WebSearch). Konfidenz-Gate ≥ 70 %. Schreibt Sub-Page (GMB) oder DB-Zeile (Mietspiegel) in Notion. Wird ausschließlich von Modul 1 / Modul 5 aufgerufen, nicht standalone. Eingeführt 2026-05-25.
---

# Sub-Skill — Marktdaten-Fallback (GMB + Mietspiegel)

## 0. Aufruf-Konvention

Dieser Skill wird NICHT standalone genutzt. Er wird ausschließlich von:
- **Modul 0 Schritt C.1** (GMB-Lookup-Fail) — Modus `gmb`
- **Modul 4 Abschnitt 2** (Mietspiegel-DB-Stadt-Fail) — Modus `mietspiegel`

aufgerufen.

**Eingang (alle Pflicht):**
- `mode`: `gmb` oder `mietspiegel`
- `stadt`: z.B. `Hagen`
- `stadtteil`: nur für GMB-Lage-Match (optional)
- `baujahr`: für Baujahres-Klasse (optional)
- `interaktiv`: bool — false in Akquise-Modus (nicht-interaktiv via `claude --print`), true in Orchestrator-Modus
- `slug`: Objekt-Slug für Audit

**Ausgang (JSON):**
```json
{
  "ergebnis": {
    "eur_per_qm": "<number | null>",
    "zusatzfelder": { "kappungsgrenze_prozent": null, "mietpreisbremse": null, "mietspiegel_typ": null }
  },
  "konfidenz_score": "<int 0..100>",
  "quellen_trail": ["..."],
  "notion_target_id": "<page-id oder row-id>",
  "begruendung": "<2-4 Sätze>",
  "fail_reason": null
}
```

## 1. Workflow

1. **CLI-Call:**
   ```bash
   cd c:\meine-projekte\Immobilien\Aufteiler\tools\marktdaten-fallback
   python orchestrator.py --mode <mode> --stadt "<Stadt>" --stadtteil "<Stadtteil>" \
     --baujahr <YYYY> --interaktiv <0|1> --slug "<slug>"
   ```
2. **Output parsen:** Der Orchestrator gibt ein JSON-Objekt auf stdout, plus eventuelle MCP-Action-Lines (siehe Schritt 3).
3. **MCP-Notion-Calls ausführen:** Für jede `action`-Zeile in der Orchestrator-Output:
   - `notion_create_page` → `mcp__notion-create-pages` aufrufen mit `parent_page_id` + `title` + `body_markdown`
   - `notion_upsert_db_row` → erst `mcp__notion-search` ob Zeile mit `Stadt=<stadt>` schon existiert; wenn ja `mcp__notion-update-page`, sonst `mcp__notion-create-pages` mit `data_source_url`
4. **Page-ID/Row-ID zurück-Patchen:** Die echte ID aus der MCP-Antwort übernehmen — Orchestrator hat `null` zurückgegeben weil er den MCP-Call nicht selbst macht.
5. **Ergebnis zurück an aufrufendes Modul:** das vollständige Result-JSON mit gefüllter `notion_target_id`.

## 2. Quellen-Kaskade (nur offiziell)

| # | Modus `gmb` | Modus `mietspiegel` |
|---|---|---|
| 1 | Notion-Page-Suche `<Stadt> Marktdaten` | Notion-DB `8b000923…` Stadt-Zeile |
| 2 | BORIS NRW Gutachterausschuss-Index | Bekannte Stadt-Mietspiegel-URLs (config.py) |
| 3 | Stadt-Webseite Gutachterausschuss-Bereich | site-restricted WebSearch `site:<stadt>.de mietspiegel pdf` |
| 4 | Geoportal NRW (INSPIRE) | WebSearch + Post-Filter Whitelist |
| 5 | site-restricted WebSearch | – |

Whitelist in `tools/marktdaten-fallback/config.py`. Off-Whitelist-Treffer werden hart abgelehnt.

## 3. Konfidenz-Gate

≥ 70 % → State-Write + Notion-Upload + Return.
< 70 % und Akquise-Modus → null + `fail_reason="konfidenz_below_gate"`.
< 70 % und Orchestrator-Modus → Modul ruft `AskUserQuestion` mit LLM-Empfehlung.

## 4. Notion-Schema

**GMB:** neue Sub-Page unter Parent `3310ae59-38e4-81f1-ad36-e8bd809d437a`, Titel `📍 <Stadt> Marktdaten (GMB <Jahr>)`, Body wie in `tools/marktdaten-fallback/notion_upload.py` `build_gmb_page_body`.

**Mietspiegel:** DB-Zeile in `collection://8b000923…`, Felder gemäß `build_mietspiegel_row_payload`. Body in DB-Zeilen-Page über `build_mietspiegel_page_body`.

## 5. Error-Pfad

Bei Hard-Fail (alle Quellen erschöpft, Extract komplett gescheitert): `fail_reason` gesetzt, `eur_per_qm: null`, kein Notion-Upload. Aufrufendes Modul entscheidet (Akquise → null + Audit; Orchestrator → AskUserQuestion).

## 6. Testing

`pytest tools/marktdaten-fallback/tests/ -v` — alle Unit-Tests grün. Smoke-Test manuell via CLI mit echter Stadt.

## 7. Doc-Pflichten

- Bei Änderungen an Whitelist: `config.py` + Tests anpassen
- Bei neuem GMB-Jahrgang: keine Code-Änderung nötig, Skill erkennt Jahres-Versionierung automatisch
- Doc-File `docs/marktdaten-fallback.md` pflegen
