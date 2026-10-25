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

Es gibt KEIN Schlafzimmer-Feld auf CHECK24.
"""

START_URL = "https://baufinanzierung.check24.de/baufinanzierung/immobilienbewertung?deviceoutput=desktop"

COOKIE_ACCEPT_CANDIDATES = [
    'button:has-text("geht klar")',
    'button:has-text("Geht klar")',
    '#check24-cookie-acceptAll',
    'button:has-text("Akzeptieren")',
    '.c24-cookie-consent-wrapper button:visible',
]
COOKIE_WRAPPER = '.c24-cookie-consent-wrapper'

RESULT_MODAL_DISMISS = [
    'button:has-text("später erinnern")',
    'button:has-text("Später erinnern")',
    'a:has-text("später erinnern")',
]

RESULT_COOKIE_OK = [
    'button:has-text("OK")',
    'button[aria-label*="OK"]',
]

FORM_SELECTS = 'select.select'
FORM_INPUTS = 'input.input'

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

RADIO_ZEITRAHMEN_1_3_MONATE = 'input[qa-ref="property-evaluation-timing-0"]'
RADIO_ZEITRAHMEN_4_6_MONATE = 'input[qa-ref="property-evaluation-timing-1"]'
RADIO_ZEITRAHMEN_MEHR_6 = 'input[qa-ref="property-evaluation-timing-2"]'

STREET_SUGGESTION_CANDIDATES = [
    'li[class*="suggestion"]',
    'li[class*="autocomplete"]',
    '[role="option"]',
    'ul[class*="suggest"] li',
    '[class*="StreetSuggestion"]',
    '[class*="streetSuggestion"]',
    '[class*="dropdown"] li',
]

SUBMIT_BUTTON = 'button[qa-ref="property-evaluation-submit-button"]'

RESULT_VALUE_PATTERN = r"(\d{1,3}(?:[.\s]\d{3})+)\s*(?:€|EUR)"

TIMEOUT_MS_DEFAULT = 30_000
TIMEOUT_MS_RESULT = 60_000
