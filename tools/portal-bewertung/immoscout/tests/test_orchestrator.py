from immoscout.orchestrator import Orchestrator, OrchestratorResult
from immoscout.stages.base import ScraperStage, ScrapeResult


class _FakeStageOK(ScraperStage):
    name = "fake_ok"
    def __init__(self, html: str) -> None:
        self.html = html
    def scrape(self, url: str) -> ScrapeResult:
        return ScrapeResult(html=self.html, final_url=url, stage_name=self.name, duration_s=0.1)


class _FakeStageBlock(ScraperStage):
    name = "fake_block"
    def scrape(self, url: str) -> ScrapeResult:
        return ScrapeResult(
            html='<html>Ich bin kein Roboter <script>_Incapsula_Resource</script></html>',
            final_url=url, stage_name=self.name, duration_s=0.1,
        )


GOOD_HTML = '<html><body><script>var keyValues = {"obj_scoutId":"1"};</script>' + 'x' * 3000 + '</body></html>'


def test_first_stage_succeeds():
    orch = Orchestrator(stages=[_FakeStageOK(GOOD_HTML)], inter_stage_pause_s=0)
    result = orch.run("https://x.de")
    assert result.success is True
    assert result.successful_stage == "fake_ok"
    assert result.stages_attempted == ["fake_ok"]


def test_blocked_stage_falls_through():
    orch = Orchestrator(stages=[_FakeStageBlock(), _FakeStageOK(GOOD_HTML)], inter_stage_pause_s=0)
    result = orch.run("https://x.de")
    assert result.success is True
    assert result.successful_stage == "fake_ok"
    assert result.stages_attempted == ["fake_block", "fake_ok"]


def test_all_blocked():
    orch = Orchestrator(stages=[_FakeStageBlock(), _FakeStageBlock()], inter_stage_pause_s=0)
    result = orch.run("https://x.de")
    assert result.success is False
    assert result.successful_stage is None
    assert result.stages_attempted == ["fake_block", "fake_block"]
