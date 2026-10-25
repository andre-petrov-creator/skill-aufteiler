# `portals/check24/` — CHECK24-Adapter

## Zweck

CHECK24-spezifischer Adapter für das Portal-Bewertung-Framework.
Erbt von `PortalBase`, implementiert `fill_form()`,
`dismiss_post_submit_modals()` und `extract_dom_colors()`.

## Files

- [portals/check24/selectors.py](../portals/check24/selectors.py) — alle CSS-/XPath-Selektoren + Option-Maps + Start-URL
- [portals/check24/portal.py](../portals/check24/portal.py) — `Check24Portal(PortalBase)`
- [tests/test_portals_check24_importable.py](../tests/test_portals_check24_importable.py) — Smoke-Tests

## Bekannte Stolpersteine

| Issue | Mitigation |
|---|---|
| Cookie-Banner mit Text „geht klar" | im Selektor-Set: `'button:has-text("geht klar")'` zuerst |
| Cookie-Banner poppt verzögert auf | `dismiss_cookies` pollt bis zu 12 s |
| Straße muss `Str.` statt `Straße` sein | `input_street_with_autocomplete` normalisiert automatisch |
| Zeitrahmen-Radio „1-3 Monate" Pflicht, sonst Submit grau | `click_radio_by_label_text("1-3 Monate", nudge_keys=True)` |
| Pfeil-Nudge nötig für React-State | `nudge_keys=True` triggert 2× rechts, 2× links, Enter |
| Submit-Button braucht großen Viewport | `BrowserConfig(viewport_width=1440, viewport_height=1600)` |
| Topzinsen-Modal nach Submit blockiert weiteres | `dismiss_post_submit_modals` klickt „später erinnern" 3× |
| Zweites Cookie-Banner unten | gleicher Hook, klickt „OK" |
| PriceHubble-iframe als Result-Container | `RESULT_FRAME_MARKER = "Marktwertermittlung"` |
| CHECK24-eigene Trend-Farben im DOM | `extract_dom_colors` liest CSS-Klassen + style.color für Quervalidierung |

## Form-Reihenfolge (13 Felder + 2 Radios)

```
1. Select Immobilientyp        → "Eigentumswohnung"
2. Select Zustand              → ZUSTAND_OPTION[d.zustand]
3. Select Ausstattung          → AUSSTATTUNG_OPTION[d.ausstattung]
4. Input PLZ                   → d.plz
5. Input Straße (Autocomplete) → input_street_with_autocomplete(d.strasse)
6. Input Hausnummer            → d.hausnr
7. Input Wohnfläche            → str(d.avg_wohnflaeche_qm)
8. Input Baujahr               → str(d.baujahr)
9. Input Zimmer                → str(d.avg_zimmer)
10. Select Badezimmer          → str(d.avg_badezimmer)
11. Select Garagenstellplätze  → "1" wenn d.hat_garage, sonst "0"
12. Select Außenstellplätze    → "1" wenn d.hat_aussenstellplatz, sonst "0"
13. Radio Kaufabsicht (kaufen)
14. Radio Zeitrahmen "1-3 Monate" (mit Tastatur-Nudge)
```

## Live-Verifikation

**Akzeptanzkriterium aus Implementierungsplan (Step 7):**

> Live-Lauf mit Prosperstr. 59 → JSON enthält `marktwert_eur_mittel`
> 170.000–180.000 € + alle drei Trend-Werte + Ampel grün

**Aufruf nach Step 8 (CLI):**

```bash
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
  --anzahl-garagen 0 `
  --anzahl-aussenstellplaetze 0 `
  --headed `
  --verbose
```

**Erwartung:** `marktwert_eur_mittel` zwischen 170.000 und 180.000 €,
`trend_ampel="gruen"`.

> **Hinweis:** Live-Verifikation muss vom User ausgeführt werden. Dieser
> Adapter ist Code-getestet, aber gegen die echte CHECK24-Site nicht in
> dieser Session verifiziert.

## Bekannte Limitierungen

- **Nur Eigentumswohnung als Immobilientyp** — der Aufteiler bewertet eine
  Durchschnitts-WE im MFH. Falls anderes nötig: `IMMOTYP_OPTION`-Map nutzen,
  aber `fill_form` erweitern.
- **Nur Kaufabsicht-Pfad getestet.** Verkaufen-Pfad funktioniert vermutlich,
  aber bei DOM-Änderungen oder weiteren Pflichtfeldern braucht das ggf.
  Anpassung.
- **Zeitrahmen ist hartcodiert auf „1-3 Monate".** Andere Optionen wurden
  nicht getestet (sind aber im Selektor-Set vorhanden, falls nötig).
- **`extract_dom_colors` ist heuristisch** — basiert auf CSS-Klassen-Namen
  (`green`, `red`, `positive`, `negative`). Bei DOM-Änderungen muss das
  ggf. nachgezogen werden. Default-Fallback: leeres Dict → Heuristik aus
  `core.parsers.trend_ampel` greift.
