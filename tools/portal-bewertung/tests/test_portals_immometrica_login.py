"""Tests fuer den Immometrica-Login gegen das v2-Formular (Stand 2026-09-10).

Hintergrund: Das Login-Formular ist auf `data-testid="v2-login-form"` umgestellt.
Die alte Text-Suche greift dort ins Leere bzw. auf falsche Elemente:

- `tab.find(text="Login")`    -> `<input id="id_login" name="login">` (E-Mail-Feld!)
- `tab.find(text="Anmelden")` -> `<h1 class="auth-title">Anmelden</h1>` (Ueberschrift)

Beide Klicks submitten nichts. Das alte `_do_login` lieferte trotzdem `True`,
wodurch der Adapter auf der Login-Seite weiterlief und alle sechs Configs mit
`submit_button_not_found` scheiterten.

Die FakePage unten modelliert genau dieses Verhalten.
"""
import asyncio
import sys
from pathlib import Path

import pytest

PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJ_ROOT))

from portals.immometrica.portal import _do_login  # noqa: E402

LOGIN_URL = "https://www.immometrica.com/de/accounts/login/?next=/de/home"
HOME_URL = "https://www.immometrica.com/de/home"

LOGIN_BODY = (
    "Zum Inhalt springen\nAnmelden\nE-Mail-Adresse\nPasswort\n"
    "Angemeldet bleiben\nAnmelden\n\noder\n\nMit Passkey anmelden"
)
HOME_BODY = "Profil\nLogout\nAndre Petrov\nHome\nMarktstatistik\nWertbericht"


class FakeElement:
    def __init__(self, page, name):
        self.page = page
        self.name = name

    async def click(self):
        self.page.click(self.name)

    async def send_keys(self, text):
        self.page.type(self.name, text)


class FakePage:
    """Modelliert das v2-Login-Formular inkl. der beobachteten find()-Fallen."""

    def __init__(self, credentials_valid=True, submit_present=True):
        self.credentials_valid = credentials_valid
        self.submit_present = submit_present
        self.logged_in = False
        self.url = LOGIN_URL
        self.fields = {"login": "", "password": ""}
        self.remember_checked = False
        self.submit_clicked = False
        self.stray_clicks = []

    def click(self, name):
        if name == "submit":
            self.submit_clicked = True
            if (self.fields["login"] and self.fields["password"]
                    and self.credentials_valid):
                self.logged_in = True
                self.url = HOME_URL
        elif name == "remember":
            self.remember_checked = not self.remember_checked
        else:
            # h1-Ueberschrift, E-Mail-Feld, Marketing-Link: kein Submit
            self.stray_clicks.append(name)

    def type(self, name, text):
        if name in self.fields:
            self.fields[name] += text

    @property
    def body_text(self):
        return HOME_BODY if self.logged_in else LOGIN_BODY


class FakeTab:
    def __init__(self, page):
        self.page = page
        self.visited = []

    async def get(self, url):
        self.visited.append(url)
        if self.page.logged_in:
            self.page.url = url
        else:
            # Nicht eingeloggt -> App-Routen leiten auf die Login-Seite um
            self.page.url = url if "/accounts/login" in url else LOGIN_URL
        return self

    async def find(self, text=None, best_match=False, timeout=None):
        """Spiegelt nodrivers Attribut-Treffer auf der echten Seite."""
        if self.page.logged_in:
            return None
        if text == "Login":
            return FakeElement(self.page, "id_login_input")
        if text == "Anmelden":
            return FakeElement(self.page, "h1_auth_title")
        if text == "Einloggen":
            return FakeElement(self.page, "marketing_link")
        return None

    async def query_selector(self, selector):
        if self.page.logged_in:
            return None
        if selector == 'input[type="email"]':
            return FakeElement(self.page, "login")
        if selector == 'input[type="password"]':
            return FakeElement(self.page, "password")
        if selector == "#id_remember":
            return FakeElement(self.page, "remember")
        if selector in ('[data-testid="v2-login-submit"]',
                        'form.auth-form button[type="submit"]'):
            return FakeElement(self.page, "submit") if self.page.submit_present else None
        return None

    async def evaluate(self, expression, **kwargs):
        if "location.href" in expression:
            return self.page.url
        if "innerText" in expression:
            return self.page.body_text
        return None


def run(coro):
    return asyncio.run(coro)


# ============================================================
# _do_login
# ============================================================

def test_do_login_clicks_the_real_submit_button():
    """Regression: der Submit-Button muss geklickt werden, nicht h1/E-Mail-Feld."""
    page = FakePage()
    ok = run(_do_login(FakeTab(page), "user@example.com", "pw"))
    assert page.submit_clicked is True
    assert ok is True


def test_do_login_fills_both_fields_before_submit():
    page = FakePage()
    run(_do_login(FakeTab(page), "user@example.com", "geheim"))
    assert page.fields["login"] == "user@example.com"
    assert page.fields["password"] == "geheim"


def test_do_login_returns_false_when_still_on_login_page():
    """Kein stilles True mehr: falsche Credentials muessen als Fehler ankommen."""
    page = FakePage(credentials_valid=False)
    ok = run(_do_login(FakeTab(page), "user@example.com", "falsch",
                       verify_timeout_s=1.0))
    assert page.submit_clicked is True
    assert ok is False


def test_do_login_returns_false_when_submit_button_missing():
    page = FakePage(submit_present=False)
    ok = run(_do_login(FakeTab(page), "user@example.com", "pw"))
    assert ok is False


def test_do_login_activates_remember_checkbox():
    """'Angemeldet bleiben' haelt die Session im persistenten Profil laenger."""
    page = FakePage()
    run(_do_login(FakeTab(page), "user@example.com", "pw"))
    assert page.remember_checked is True


def test_do_login_does_not_click_heading_or_email_field():
    page = FakePage()
    run(_do_login(FakeTab(page), "user@example.com", "pw"))
    assert "h1_auth_title" not in page.stray_clicks
    assert "id_login_input" not in page.stray_clicks


@pytest.mark.parametrize("creds", [("", "pw"), ("user@example.com", "")])
def test_do_login_returns_false_on_empty_credentials(creds):
    page = FakePage()
    ok = run(_do_login(FakeTab(page), creds[0], creds[1]))
    assert ok is False
