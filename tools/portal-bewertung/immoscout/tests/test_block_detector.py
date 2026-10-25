from pathlib import Path

from immoscout.block_detector import BlockDetector

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_imperva_block_is_detected():
    detector = BlockDetector()
    html = _read("imperva_block.html")
    decision = detector.evaluate(html=html, status_code=200, headers={}, final_url="https://www.immobilienscout24.de/expose/123")
    assert decision.blocked is True
    assert "imperva_text" in decision.markers
    assert "incapsula_url" in decision.markers
    assert len(decision.markers) >= 2


def test_valid_expose_is_not_blocked():
    detector = BlockDetector()
    html = _read("valid_expose.html")
    decision = detector.evaluate(html=html, status_code=200, headers={}, final_url="https://www.immobilienscout24.de/expose/167669914")
    assert decision.blocked is False
    assert decision.markers == []


def test_one_marker_is_not_enough():
    detector = BlockDetector()
    decision = detector.evaluate(html="short", status_code=200, headers={}, final_url="https://x.de")
    # short_body + no_keyvalues = 2 markers → blocked
    assert decision.blocked is True


def test_status_403_plus_xinfo_marks_block():
    detector = BlockDetector()
    decision = detector.evaluate(
        html="some content with keyValues = {} placeholder",
        status_code=403,
        headers={"X-Iinfo": "1-2345-NN"},
        final_url="https://x.de",
    )
    assert decision.blocked is True
    assert "http_4xx" in decision.markers
    assert "xinfo_header" in decision.markers
