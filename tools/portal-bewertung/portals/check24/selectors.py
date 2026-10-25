"""Zentrale DOM-Selektoren für das CHECK24-Bewertungsformular.

Stand: 2026-05-14 — DOM live verifiziert via inspect_form.py.

Echte Reihenfolge (Index-basiert):

INPUTS (input.input, maxlength angegeben):
  0  Postleitzahl (5)
  1  Straße        (∞)
  2  Nr.           (∞)
  3  Gesamte Wohnfläche (3)
  4  Baujahr       (4)
  5  Zimmer        (2)         ← KEIN Select!

SELECTS (select.select):
  0  Immobilientyp
  1  Zustand der Immobilie
  2  Ausstattung der Immobilie
  3  Badezimmer            (1/2/3/4/5)
  4  Garagenstellplätze    (0/1/2)
  5  Außenstellplätze      (0/1/2)

RADIOS:
  purpose-0 = Kaufen
  purpose-1 = Verkaufen
  timing-0  = 1-3 Monate (Pflicht für Submit-Enable!)

Es gibt KEIN Schlafzimmer-Feld auf CHECK24.
"""

START_URL = (
    "https://baufinanzierung.check24.de/baufinanzierung/immobilienbewertung"
    "?deviceoutput=desktop"
)

COOKIE_ACCEPT_CANDIDATES = [
    # Aktuelle CHECK24-Variante (2026-05-20): zwei <a class="c24-cookie-consent-button">
    # nebeneinander — 'anpassen' (c24-cookie-consent-button-secondary, oeffnet
    # Detail-Dialog) UND 'geht klar' (Primary, ruft giveConsent('fam')).
    # WICHTIG: secondary ausschliessen, sonst clickt .first den anpassen-Link
    # und der Detail-Dialog ueberlagert die Form (Form-Submit feuert dann nie).
    "a.c24-cookie-consent-button:not(.c24-cookie-consent-button-secondary)",
    'a:has-text("geht klar")',
    'button:has-text("geht klar")',
    'button:has-text("Geht klar")',
    "#check24-cookie-acceptAll",
    'button:has-text("Akzeptieren")',
    # Fallback fuer den Fall, dass der Detail-Dialog doch je auftaucht:
    'button:has-text("alle akzeptieren")',
    'a:has-text("alle akzeptieren")',
    ".c24-cookie-consent-wrapper button:visible",
]
COOKIE_WRAPPER = ".c24-cookie-consent-wrapper"
COOKIE_FALLBACK_REMOVE = [
    ".c24-cookie-consent-wrapper",
    ".c24-strict-blocking-layer",
]

RESULT_MODAL_DISMISS = [
    'button:has-text("später erinnern")',
    'button:has-text("Später erinnern")',
    'a:has-text("später erinnern")',
]
RESULT_COOKIE_OK = [
    'button:has-text("OK"):visible',
    'button[aria-label="OK"]',
]

FORM_SELECTS = "select.select"
FORM_INPUTS = "input.input"

INPUT_PLZ = 0
INPUT_STRASSE = 1
INPUT_HAUSNR = 2
INPUT_WOHNFLAECHE = 3
INPUT_BAUJAHR = 4
INPUT_ZIMMER = 5

SELECT_IMMOTYP = 0
SELECT_ZUSTAND = 1
SELECT_AUSSTATTUNG = 2
SELECT_BADEZIMMER = 3
SELECT_GARAGEN = 4
SELECT_AUSSENSTELLPLATZ = 5

IMMOTYP_OPTION = {
    "wohnung": "Eigentumswohnung",
    "einfamilienhaus": "Einfamilienhaus",
    "doppelhaus": "Doppelhaushälfte",
    "reihenmittelhaus": "Reihenmittelhaus",
    "reiheneckhaus": "Reiheneckhaus",
    "mehrfamilienhaus": "Mehrfamilienhaus",
}

ZUSTAND_OPTION = {
    "renovierungsbeduerftig": "renovierungsbedürftig",
    "gut": "gut erhalten",
    "neu": "neu / kürzlich renoviert",
}

AUSSTATTUNG_OPTION = {
    "einfach": "einfach",
    "normal": "normal",
    "gehoben": "gehoben",
    "luxus": "luxuriös",
}

RADIO_KAUFEN = 'input[qa-ref="property-evaluation-purpose-0"]'
RADIO_VERKAUFEN = 'input[qa-ref="property-evaluation-purpose-1"]'

RADIO_ZEITRAHMEN_1_3_MONATE_LABEL = "1-3 Monate"

SUBMIT_BUTTON = 'button[qa-ref="property-evaluation-submit-button"]'

RESULT_FRAME_MARKER = "Marktwertermittlung"

# PriceHubble-iframe (Result-Container) hat ein eigenes Cookie-Consent-Banner.
# Solange der OK-Button nicht geklickt wird, rendert PH keinen Marktwert-
# Inhalt, und find_result_frame triggert auf 'Marktwertermittlung' nicht.
PRICEHUBBLE_FRAME_URL_HINTS = ("pricehubble", "dossier")
PRICEHUBBLE_CONSENT_BUTTON = "button.ph-ds-consent__button"
