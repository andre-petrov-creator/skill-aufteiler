from immoscout.stages.base import ScrapeResult


def test_scraperesult_holds_html_and_url():
    r = ScrapeResult(html="<html>x</html>", final_url="https://x.de", stage_name="test", duration_s=1.5)
    assert r.html == "<html>x</html>"
    assert r.final_url == "https://x.de"
    assert r.stage_name == "test"
    assert r.duration_s == 1.5
    assert r.error is None


def test_scraperesult_with_error():
    r = ScrapeResult(html="", final_url="", stage_name="test", duration_s=0.0, error="timeout")
    assert r.error == "timeout"
