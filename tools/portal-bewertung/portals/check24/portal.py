"""CHECK24-Portal-Adapter — Form-Befüllung + Post-Submit-Modal-Behandlung.

Konsumiert einen `GeneralisierterDatensatz`, befüllt das CHECK24-Formular in
der korrekten Reihenfolge (6 Selects + 6 Inputs + Kaufen-Radio +
Zeitrahmen-Klick mit Pfeil-Nudge). Nach Submit werden Topzinsen-Modal und
zweites Cookie-Banner geschlossen.

Vom User verifizierte Eigenheiten:
- 'Straße' muss als 'Str.' geschrieben sein (Geo-Autocomplete-Erwartung)
- Zeitrahmen-Radio braucht Tastatur-Nudge, sonst bleibt Submit grau
- CHECK24-Cookie-Banner kann verzögert aufpoppen
"""
from __future__ import annotations

import time
from typing import Any, Optional

from core.datensatz import GeneralisierterDatensatz
from core.inputs import input_street_with_autocomplete, input_typed
from core.log import log
from core.modals import dismiss_modal_by_text
from core.portal_base import PortalBase, RunConfig
from core.radios import click_radio, click_radio_by_label_text
from core.selects import select_by_index

from . import selectors as sel


class Check24Portal(PortalBase):
    NAME = "check24"
    START_URL = sel.START_URL
    COOKIE_ACCEPT_CANDIDATES = sel.COOKIE_ACCEPT_CANDIDATES
    COOKIE_WRAPPER = sel.COOKIE_WRAPPER
    SUBMIT_SELECTOR = sel.SUBMIT_BUTTON
    RESULT_FRAME_MARKER = sel.RESULT_FRAME_MARKER

    def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
        # 3 Selects oben: Typ, Zustand, Ausstattung
        select_by_index(
            page, sel.FORM_SELECTS, sel.SELECT_IMMOTYP, sel.IMMOTYP_OPTION["wohnung"]
        )
        select_by_index(
            page, sel.FORM_SELECTS, sel.SELECT_ZUSTAND, sel.ZUSTAND_OPTION[d.zustand]
        )
        select_by_index(
            page,
            sel.FORM_SELECTS,
            sel.SELECT_AUSSTATTUNG,
            sel.AUSSTATTUNG_OPTION[d.ausstattung],
        )

        # PLZ
        input_typed(page, sel.FORM_INPUTS, d.plz, index=sel.INPUT_PLZ)

        # Straße mit Autocomplete (Str.-Normalisierung)
        input_street_with_autocomplete(
            page, sel.FORM_INPUTS, d.strasse, index=sel.INPUT_STRASSE
        )

        # Restliche Inputs
        input_typed(page, sel.FORM_INPUTS, d.hausnr, index=sel.INPUT_HAUSNR)
        input_typed(
            page,
            sel.FORM_INPUTS,
            str(d.avg_wohnflaeche_qm),
            index=sel.INPUT_WOHNFLAECHE,
        )
        input_typed(page, sel.FORM_INPUTS, str(d.baujahr), index=sel.INPUT_BAUJAHR)
        input_typed(page, sel.FORM_INPUTS, str(d.avg_zimmer), index=sel.INPUT_ZIMMER)

        # 3 Selects unten: Badezimmer, Garagen, Außenstellplatz
        select_by_index(
            page,
            sel.FORM_SELECTS,
            sel.SELECT_BADEZIMMER,
            str(d.avg_badezimmer),
        )
        select_by_index(
            page,
            sel.FORM_SELECTS,
            sel.SELECT_GARAGEN,
            "1" if d.hat_garage else "0",
        )
        select_by_index(
            page,
            sel.FORM_SELECTS,
            sel.SELECT_AUSSENSTELLPLATZ,
            "1" if d.hat_aussenstellplatz else "0",
        )

        # Kaufabsicht-Radio
        radio_sel = sel.RADIO_KAUFEN if cfg.kaufabsicht == "kauf" else sel.RADIO_VERKAUFEN
        click_radio(page, radio_sel, nudge_keys=False)
        page.wait_for_timeout(1_000)

        # Zeitrahmen-Radio (Pflicht für Submit-Enable)
        click_radio_by_label_text(
            page, sel.RADIO_ZEITRAHMEN_1_3_MONATE_LABEL, nudge_keys=True
        )

    def dismiss_post_submit_modals(self, page: Any) -> None:
        """Topzinsen-Modal + zweites Cookie-Banner + PriceHubble-iframe-Consent.

        PriceHubble rendert das Marktwert-Dashboard im iframe nur NACH eigener
        Cookie-Akzeptanz (Button `button.ph-ds-consent__button`). Ohne diesen
        Click bleibt das iframe-Body bei 'Wir verwenden Cookies...', und
        `find_result_frame` triggert auf 'Marktwertermittlung' nie.
        """
        for _ in range(3):
            dismiss_modal_by_text(
                page,
                accept_texts=["später erinnern", "Später erinnern"],
                click_timeout_ms=3_000,
                settle_ms=800,
            )
            page.wait_for_timeout(500)
        dismiss_modal_by_text(
            page, accept_texts=["OK"], click_timeout_ms=2_000, settle_ms=400
        )
        self._dismiss_pricehubble_consent(page)

    def _dismiss_pricehubble_consent(self, page: Any, max_wait_s: float = 20.0) -> bool:
        """Sucht das PriceHubble-iframe und klickt drin den OK-Button.

        Pollt bis zu `max_wait_s`, weil der iframe asynchron nachgeladen wird
        und das Consent-Banner ein paar Sekunden braucht, bis es sichtbar ist.
        """
        deadline = time.monotonic() + max_wait_s
        while time.monotonic() < deadline:
            for fr in page.frames:
                url = fr.url or ""
                if not any(h in url for h in sel.PRICEHUBBLE_FRAME_URL_HINTS):
                    continue
                try:
                    btn = fr.locator(sel.PRICEHUBBLE_CONSENT_BUTTON).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=3_000)
                        log("PriceHubble-Consent geklickt.")
                        page.wait_for_timeout(1_500)
                        return True
                except Exception:
                    continue
            page.wait_for_timeout(800)
        log("PriceHubble-Consent nicht gefunden (oder schon weg).")
        return False

    def extract_dom_colors(self, page: Any) -> dict[str, Optional[str]]:
        """Liest CHECK24-eigene Trend-Farben aus dem DOM (für Quervalidierung).

        CHECK24 färbt Trend-Werte selbst grün/gelb/rot über CSS-Klassen.
        """
        try:
            colors = page.evaluate(
                """() => {
                    const out = {jahre_3: null, jahr_1: null, prognose: null};
                    const labels = [
                        {key: 'jahre_3', match: ['3 Jahren', 'letzten 3']},
                        {key: 'jahr_1', match: ['letztem Jahr', 'Seit letztem']},
                        {key: 'prognose', match: ['Prognose', 'nächste']},
                    ];
                    document.querySelectorAll('*').forEach(el => {
                        const txt = (el.textContent || '').trim();
                        if (txt.length > 200) return;
                        for (const lbl of labels) {
                            if (lbl.match.some(m => txt.includes(m)) && out[lbl.key] === null) {
                                const container = el.closest('div, li, section') || el.parentElement;
                                if (!container) continue;
                                const percentEl = container.querySelector(
                                    '[class*="green"], [class*="yellow"], [class*="red"], '
                                    + '[class*="positive"], [class*="negative"], [style*="color"]'
                                );
                                if (percentEl) {
                                    const cls = (percentEl.className || '').toString().toLowerCase();
                                    const style = (percentEl.getAttribute('style') || '').toLowerCase();
                                    if (cls.includes('green') || cls.includes('positive') || style.includes('green')) out[lbl.key] = 'gruen';
                                    else if (cls.includes('yellow') || cls.includes('orange') || style.includes('yellow') || style.includes('orange')) out[lbl.key] = 'gelb';
                                    else if (cls.includes('red') || cls.includes('negative') || style.includes('red')) out[lbl.key] = 'rot';
                                }
                            }
                        }
                    });
                    return out;
                }"""
            )
            return colors or {"jahre_3": None, "jahr_1": None, "prognose": None}
        except Exception:
            return {"jahre_3": None, "jahr_1": None, "prognose": None}
