"""DOM-Selektoren + Wizard-Konstanten fuer interhyp.de/rechner/immobilienbewertung.

Stand: 2026-05-15 — live verifiziert via inspectors/probe_interhyp.py.

Architektur-Eigenheit: Interhyp hat einen 9-Schritt-Wizard mit Auto-Advance
auf Karten-Schritten (Step 1, 3, 8) und 'Weiter'-Button-Schritten (2, 5, 6,
7, 9). KEIN Deep-Link wie Homeday — der Adapter klickt komplett durch.

Submit-Button-Text: 'Ergebnisse anzeigen' (statt 'Weiter') beim letzten Schritt.

Result-Marker: 'Ihr Immobilienwert betraegt' eindeutig auf Zusammenfassung-Tab.
KEIN iframe — Werte werden aus dem Page-Body per Regex extrahiert.
"""
from __future__ import annotations

START_URL = "https://www.interhyp.de/rechner/immobilienbewertung/"

COOKIE_ACCEPT_CANDIDATES = [
    'button:has-text("Akzeptieren")',
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Zustimmen")',
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
]
COOKIE_WRAPPER = ""  # Interhyp nutzt kein konsistentes Wrapper-Element

# Result-Marker: Heading auf Zusammenfassung-Tab, eindeutig.
RESULT_FRAME_MARKER = "Ihr Immobilienwert"

# Wizard-Label-Konstanten (deutsche Karten-/Button-Texte)
STEP1_IMMOBILIENART = "Eigentumswohnung"
STEP3_BEWEGGRUND = "Kauf (Kapitalanlage)"

# Mapping: GeneralisierterDatensatz.ausstattung -> Interhyp-Karten-Text
STEP8_AUSSTATTUNG_MAP: dict[str, str] = {
    "einfach": "Einfach",
    "normal": "Einfach",
    "gehoben": "Gehoben",
    "luxus": "Luxus",
}

SUBMIT_TEXT_WIZARD = "Ergebnisse anzeigen"

# Body-Text-Marker, gegen den die Adapter-Logik die Ergebnis-Seite verifiziert
RESULT_BODY_MARKER = "Schätzwert"
