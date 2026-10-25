# Step 14 Handover — Immometrica (statt IS24)

> **Übergabe an neue Claude-Code-Session.** Stand: 2026-05-19.
> Lies dieses File komplett, BEVOR du an Step 14 weiterarbeitest. Dann
> `CLAUDE.md` + `DEVELOPMENT_GUIDELINES.md` + `Implementierungsplan.md` lesen.

---

## TL;DR

- **IS24 gestrichen.** Anonymer API-Wert nur PLZ-Regional (189k €), eingeloggt
  171k € — Differenz 10%, für Konsens unbrauchbar. Login-Scraping = Account-Risiko.
  Wizard-Selektoren und Usercentrics-Bypass sind dokumentiert in
  `inspectors/probe_immoscout24.py` und den DOM-Dumps unter `runs/2026-05-17T08*`.
- **Immometrica neu im Plan**, ersetzt IS24 als 4. Portal. Hat Login, aber
  liefert auch Miete + Rendite + Marktstatistik (mehr Daten als jedes andere Portal).
- **User hat Account.** Credentials in `.env` (gitignored).
- **Bisheriger Probe scheitert am 2-Step-Login.** Die `/de/login`-Page zeigt nur
  E-Mail-Feld; das Passwort kommt vermutlich auf einer Folgeseite (Modal-Newsletter
  hat den ersten Versuch zusätzlich gestört).

---

## Was Immometrica liefern soll (Eingeloggter Zustand, aus User-Screenshots)

Pro Adresse (Beispiel Prosperstr. 59, 45357 Essen, 80 m², 3 Zi.):

| Feld | Beispiel | Bemerkung |
|---|---|---|
| Marktwert (Schätzwert) | 171.000 € | „gemittelt" |
| €/m² | 2.138 €/m² | „pro m²" |
| Geschätzte Miete | 701 €/Monat | „9 €/m²" |
| Mietprognose 6 Monate | +2,6 % | mit +18 € Veränderung |
| Mietprognose 3 Monate | +0,6 % | mit +4 € Veränderung |
| Rendite (Brutto-Mietrendite) | ~4,9 % | „im gehobenen Bereich" |
| Marktangebote zum Kauf | 38 | im Umkreis |
| Marktangebote zur Miete | 62 | im Umkreis |
| Passende Suchaufträge Kauf | 919 | |
| Passende Suchaufträge Miete | 2.358 | |

Plus optional: Wertentwicklungs-Chart (Vergleich Q3 2023 bis Q2 2027 Prognose).

Diese Felder sind **alle aus den User-Screenshots vom 2026-05-19** rekonstruiert.

---

## Was bisher exploriert wurde

### Existierende Inspector-/Probe-Files
- `inspectors/probe_immometrica.py` — erster Login+Search-Versuch, scheitert
  bei „Login-Felder nicht gefunden" (Passwort-Feld fehlt auf der Initial-Page)
- `inspectors/open_portal.py` — generischer Browser-Open-Halter, funktioniert
- `inspectors/record_state.py` — Storage-State-Recorder (NICHT für Immometrica
  empfohlen, weil Login-State eh ablaufen würde)

### Letzte Probe-Lauf-Erkenntnisse (Run `b77lkcztb`, 2026-05-19T0745)
- Home-Page (https://www.immometrica.com/de) zeigt direkt ein Newsletter-Modal
  („Anmeldung für den nächsten ImmoMetrica-Live-Workshop") über dem Cookie-Banner
- Anmelden-Link gefunden via `a:has-text("Anmelden")`
- Login-Page zeigt NUR ein E-Mail-Feld (input[type="email"]) — KEIN Passwort
- Probe scheitert hier, klickt Submit ohne Passwort, landet auf Search-Page
- Network-Log: nur 2 Einträge (kaum API-Calls erfasst)

### Wahrscheinlich richtiger Login-Flow
1. Newsletter-Modal wegklicken (X-Button rechts oben)
2. Cookie-Banner akzeptieren
3. Anmelden-Link in Header klicken (oder `https://app.immometrica.com/de/login`
   direkt — App-Subdomain prüfen)
4. E-Mail eingeben + Weiter
5. Passwort auf nächster Page eingeben + Anmelden
6. Auf Dashboard / Search landen

### Credentials (Stand 2026-05-19)
- `.env` enthält `IMMOMETRICA_USERNAME` + `IMMOMETRICA_PASSWORD`
- `.env.example` hat die Vorlage committet, `.env` ist gitignored
- User hat das Passwort im Chat-Verlauf geteilt — sollte nach Abschluss
  ändern (Security-Hygiene)

---

## Konkrete nächste Schritte für die neue Session

### Phase A — Login richtig hinbekommen
1. Start mit `open_portal.py https://www.immometrica.com/de --name immometrica`
   (User klickt sich live durch, sammelt Selektoren für Newsletter-Close,
   Cookie-Accept, Anmelden-Link, E-Mail-Feld, Passwort-Feld)
2. User-Screenshots pro Step holen (analog Sparring Step 13 Interhyp)
3. `probe_immometrica.py` umbauen:
   - Schritt 1: Newsletter-Modal close (X-Selektor) + Cookie dismiss
   - Schritt 2: Anmelden-Link click
   - Schritt 3: E-Mail eingeben + Weiter click
   - Schritt 4: WAIT für Password-Page (`page.wait_for_selector('input[type=password]')`)
   - Schritt 5: Passwort eingeben + Anmelden click
   - Schritt 6: WAIT für Dashboard / `/app` / `/search`
4. Storage-State nach erfolgreichem Login speichern (für künftige Probe-Läufe)

### Phase B — Adress-Suche + Network-Sniffer
1. Auf der eingeloggten Search-Page Adresse eingeben (Prosperstr. 59)
2. Autocomplete-Dropdown + Result-Page Screenshots sammeln
3. Network-Sniffer protokolliert alle `/api/`-Calls (JSON-Response)
4. Identifizieren des „Detail-Endpoint" der Marktwert + Miete + Rendite
   liefert (vermutlich GET mit Adress-ID oder POST mit Adress-Daten)

### Phase C — Adapter bauen
1. `portals/immometrica/__init__.py`, `selectors.py`, `parsers.py`, `portal.py`
2. `portal.py` mit Login-Step im `fill_form` (oder besser: eigener
   `pre_login`-Hook in PortalBase erweitern, weil Login einmalig pro Session)
3. Schema-Erweiterung im `RunResult.extra`-Slot (Felder aus „Was Immometrica
   liefern soll" oben)
4. `core/portal_base.py` ggf. um optional `requires_login`-Flag und
   `login(ctx, page)`-Hook erweitern (saubere Architektur)
5. PORTAL_REGISTRY in `m00_portal_pricer.py` um `immometrica` erweitern

### Phase D — Tests + Doku
1. Parser-Tests TDD (Body-Text-Samples aus den Probe-Network-Dumps)
2. Smoke-Tests für PORTAL_REGISTRY
3. `docs/portal-immometrica.md` analog Interhyp-Doku
4. Live-Lauf headed, dann headless verifizieren
5. Implementierungsplan.md: Step 14 als `[x]` markieren

### Phase E — Adress-Validierungs-Loop
Siehe Memory [[immoscout24-adresse-validierung]] — gilt für Immometrica analog:
nach Result-Load die im Body sichtbare Adresse mit dem Datensatz vergleichen,
bei Mismatch error_code=`address_mismatch`.

---

## Wichtige Architektur-Entscheidungen, die geklärt werden müssen

1. **Login-Hook in PortalBase?** Aktuell hat PortalBase keine Login-Methode.
   Empfehlung: Neuer optionaler Hook `login(ctx, page) -> None` in PortalBase,
   default = no-op. Immometrica überschreibt ihn. Storage-State im Adapter
   cachen, um Login-Frequenz zu reduzieren.

2. **Schema-Erweiterung**: Marktwert kommt ins Top-Level (CHECK24-Pattern via
   `parse_marktwert`-Override), alle Immometrica-Spezifika (Miete, Rendite,
   Marktstatistik) ins `extra`. Analog Interhyp.

3. **Modul-0-Integration**: Wenn Immometrica auch Miete liefert, kann das Modul 4
   (Mietsituation) eine zusätzliche Quervalidierungs-Quelle bekommen. Aber
   nicht jetzt — Step 16-17 später.

4. **Konsens-Median**: Immometrica's Marktwert ist OBJEKTSPEZIFISCH (anders als
   IS24-anonym). Daher in den 4-Portal-Konsens vollwertig einbeziehbar.

5. **Wichtig — Memory-Bezüge**:
   - [[immobilien-portale-strassen-kurzform]] — Straßen-Kurzform-Logik („Str."
     statt „Straße") prüfen, ob Immometrica das auch braucht
   - [[portal-bewertung-blueprint-workflow]] — gehört aktualisiert nach Step 14
   - [[immoscout24-adresse-validierung]] — gilt für Immometrica analog

---

## Was NICHT in Step 14 gehört

- `portals/immoscout24/` löschen → in Step 9 enthalten (Cleanup), nicht hier
- Den Bestand-Ist nicht verbessern — nur Immometrica neu bauen
- IS24-Reverse-Engineering fortsetzen (verworfen)

---

## Memory-Updates für die neue Session

Folgende Memory-Files existieren bereits oder müssen aktualisiert werden:

1. `project_immoscout24-adresse-validierung.md` — existiert, gilt analog für
   Immometrica
2. `project_portal-bewertung-blueprint-workflow.md` — Stand-Update: Step 14
   = Immometrica
3. `project_portal-bewertung-step-14-immometrica.md` — NEU: dieses Handover
   in komprimierter Form als Memory

---

## Files am Ende dieser Session

```
tools/portal-bewertung/
├── .env                                  # NEU (gitignored)
├── .env.example                          # IMMOMETRICA_USERNAME/PASSWORD ergänzt
├── Implementierungsplan.md               # Step 14 = Immometrica statt IS24
├── HANDOVER_step-14_immometrica.md       # NEU (dieses File)
├── inspectors/
│   ├── probe_immometrica.py              # NEU (Login + Search, scheitert Phase A)
│   ├── probe_immoscout24.py              # IS24-Explorer (Referenz)
│   └── record_state.py                   # NEU (Storage-State-Recorder)
└── runs/                                 # Screenshots + DOM-Dumps + Network-Logs
    └── 2026-05-19T0745*_immometrica_*    # Letzter Immometrica-Probe-Lauf
```

Memory-Verzeichnis:
```
~/.claude/projects/c--meine-projekte/memory/
└── project_immoscout24-adresse-validierung.md  # NEU
```
