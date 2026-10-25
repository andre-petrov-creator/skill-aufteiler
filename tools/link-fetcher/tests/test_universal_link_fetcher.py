"""Unit-Tests fuer link-fetcher Helper-Funktionen (ohne Live-Requests)."""
import sys
from pathlib import Path

# link-fetcher hat Bindestrich → kein Package-Import moeglich. sys.path-Hack.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stages import has_captcha_marker, is_likely_property_image  # noqa: E402


def test_has_captcha_marker_detects_imperva_de():
    html = "<html><body>...Ich bin kein Roboter...</body></html>"
    assert has_captcha_marker(html) is True


def test_has_captcha_marker_detects_imperva_en():
    html = "<html>Pardon Our Interruption</html>"
    assert has_captcha_marker(html) is True


def test_has_captcha_marker_detects_cloudflare_block():
    html = "<html>Attention Required! | Cloudflare</html>"
    assert has_captcha_marker(html) is True


def test_has_captcha_marker_negative_normal_page():
    html = "<html>Schoene Wohnung mit Balkon</html>"
    assert has_captcha_marker(html) is False


def test_has_captcha_marker_empty():
    assert has_captcha_marker("") is False
    assert has_captcha_marker(None) is False


def test_has_captcha_marker_negative_form_recaptcha():
    """reCAPTCHA als Form-Schutz (Library im Footer) ist KEIN Block."""
    html = (
        "<html><head><script src='https://www.recaptcha.net/recaptcha/enterprise.js'>"
        "</script></head><body>" + "Schoene 4-Zimmer-Wohnung in zentraler Lage. " * 200
        + "<form><input data-sitekey='6Lfr...'/></form></body></html>"
    )
    assert has_captcha_marker(html) is False


def test_has_captcha_marker_positive_short_with_sitekey():
    """Kurzes HTML mit sitekey = Challenge-Seite."""
    html = "<html><body><div data-sitekey='abc123'></div></body></html>"
    assert has_captcha_marker(html) is True


def test_is_likely_property_image_skips_logo():
    assert is_likely_property_image("https://cdn.example.com/logo.png") is False


def test_is_likely_property_image_accepts_cdn_pattern():
    url = "https://d1234.cloudfront.net/listings/abc123/image_full.jpg"
    assert is_likely_property_image(url) is True


def test_is_likely_property_image_skips_data_uri():
    assert is_likely_property_image("data:image/png;base64,iVBORw0KG...") is False
