"""Smoke-Test: Playwright-Helper-Module müssen ohne Fehler importierbar sein.

Unit-Tests für die Helpers selbst sind nicht sinnvoll (sie machen DOM-Interaktion).
Verifikation erfolgt live via Step 7 (CHECK24-Migration).
"""


def test_browser_module_imports() -> None:
    from core import browser

    assert hasattr(browser, "launch_browser")
    assert hasattr(browser, "BrowserConfig")


def test_cookies_module_imports() -> None:
    from core import cookies

    assert hasattr(cookies, "dismiss_cookies")


def test_inputs_module_imports() -> None:
    from core import inputs

    assert hasattr(inputs, "input_typed")
    assert hasattr(inputs, "input_street_with_autocomplete")
    assert hasattr(inputs, "normalize_strasse_abbrev")


def test_radios_module_imports() -> None:
    from core import radios

    assert hasattr(radios, "click_radio")
    assert hasattr(radios, "click_radio_by_label_text")


def test_selects_module_imports() -> None:
    from core import selects

    assert hasattr(selects, "select_by_index")
    assert hasattr(selects, "select_by_label")


def test_submit_module_imports() -> None:
    from core import submit

    assert hasattr(submit, "wait_for_enabled_submit")
    assert hasattr(submit, "click_submit")


def test_reader_module_imports() -> None:
    from core import reader

    assert hasattr(reader, "find_result_frame")
    assert hasattr(reader, "deep_scroll_frame")
    assert hasattr(reader, "read_frame_body_deep")
    assert hasattr(reader, "read_page_body_deep")


def test_log_module_imports() -> None:
    from core import log as log_mod

    assert hasattr(log_mod, "log")
    assert hasattr(log_mod, "set_verbose")


def test_normalize_strasse_abbrev_replaces_strasse_with_str() -> None:
    from core.inputs import normalize_strasse_abbrev

    assert normalize_strasse_abbrev("Prosperstraße") == "Prosperstr."
    assert normalize_strasse_abbrev("Prosperstrasse") == "Prosperstr."
    assert normalize_strasse_abbrev("Bahnhofstraße 5") == "Bahnhofstr. 5"
    # Schon abgekürzt → unverändert
    assert normalize_strasse_abbrev("Prosperstr.") == "Prosperstr."
    # Keine Straße im Namen → unverändert
    assert normalize_strasse_abbrev("Am Hang") == "Am Hang"
