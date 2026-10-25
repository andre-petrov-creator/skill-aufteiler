"""Smoke-Test für Runner-Orchestrierung mit Dummy-Portal + FakePage."""
from __future__ import annotations

from typing import Any

import pytest

from core.datensatz import GeneralisierterDatensatz
from core.portal_base import PortalBase, RunConfig, RunResult
from core.runner import run_with_page


class FakeLocator:
    def __init__(
        self,
        *,
        count: int = 1,
        visible: bool = True,
        text: str = "",
        enabled: bool = True,
    ) -> None:
        self._count = count
        self._visible = visible
        self._text = text
        self._enabled = enabled
        self.clicked = False

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return self._count

    def is_visible(self) -> bool:
        return self._visible

    def is_enabled(self, timeout: int = 0) -> bool:
        return self._enabled

    def get_attribute(self, name: str) -> Any:
        return None

    def click(self, **kwargs: Any) -> None:
        self.clicked = True

    def scroll_into_view_if_needed(self, **kwargs: Any) -> None:
        pass

    def wait_for(self, **kwargs: Any) -> None:
        pass

    def inner_text(self, **kwargs: Any) -> str:
        return self._text


class FakeFrame:
    def __init__(self, body_text: str) -> None:
        self._body_text = body_text
        self.url = "about:blank"

    def locator(self, _selector: str) -> FakeLocator:
        return FakeLocator(text=self._body_text)

    def evaluate(self, _script: str, *args: Any) -> str:
        return self._body_text


class FakePage:
    def __init__(self, frame_body: str = "", url: str = "about:blank") -> None:
        self.url = url
        self.goto_calls: list[str] = []
        self.wait_calls: list[int] = []
        self.screenshots: list[str] = []
        self._frame = FakeFrame(frame_body)

    def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_calls.append(url)
        self.url = url

    def locator(self, _selector: str) -> FakeLocator:
        return FakeLocator(text="")

    def wait_for_timeout(self, ms: int) -> None:
        self.wait_calls.append(ms)

    def wait_for_selector(self, _selector: str, **kwargs: Any) -> None:
        pass

    def set_default_timeout(self, _ms: int) -> None:
        pass

    @property
    def frames(self) -> list[FakeFrame]:
        return [self._frame]

    def evaluate(self, _script: str, *args: Any) -> str:
        return ""

    def screenshot(self, path: str = "", **kwargs: Any) -> None:
        self.screenshots.append(path)


class DummyPortal(PortalBase):
    NAME = "dummy"
    START_URL = "https://example.de/start"
    COOKIE_ACCEPT_CANDIDATES: list[str] = []
    COOKIE_WRAPPER: str = ""
    SUBMIT_SELECTOR = "button.submit"
    RESULT_FRAME_MARKER = "Marktwertermittlung"

    def __init__(self) -> None:
        self.fill_calls: list[GeneralisierterDatensatz] = []
        self.dismiss_calls: int = 0

    def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
        self.fill_calls.append(d)

    def dismiss_post_submit_modals(self, page: Any) -> None:
        self.dismiss_calls += 1


@pytest.fixture
def datensatz() -> GeneralisierterDatensatz:
    return GeneralisierterDatensatz(
        strasse="Prosperstr.",
        hausnr="59",
        plz="45357",
        ort="Essen",
        baujahr=1965,
        zustand="gut",
        ausstattung="normal",
        anzahl_we=4,
        avg_wohnflaeche_qm=80,
        avg_zimmer=3,
    )


def test_runner_calls_portal_hooks_in_order(datensatz: GeneralisierterDatensatz) -> None:
    frame_text = (
        "Marktwertermittlung\n"
        "Marktwert\n173.000 €\n"
        "Marktwertspanne\n168.000 - 178.000 €\n"
        "Zeitverlauf "
        "+6,7 % In den letzten 3 Jahren "
        "+3,0 % Seit letztem Jahr "
        "+1,4 % Prognose für das nächste Jahr"
    )
    page = FakePage(frame_body=frame_text, url="https://example.de/start")
    portal = DummyPortal()

    result = run_with_page(portal, datensatz, page, RunConfig(verbose=False))

    assert page.goto_calls == ["https://example.de/start"]
    assert portal.fill_calls == [datensatz]
    assert portal.dismiss_calls == 1
    assert isinstance(result, RunResult)
    assert result.status == "ok"
    assert result.portal == "dummy"
    assert result.marktwert_eur_mittel == 173_000
    assert result.marktwert_eur_min == 168_000
    assert result.marktwert_eur_max == 178_000
    assert result.trends["jahre_3"] == 6.7
    assert result.trend_ampel == "gruen"


def test_runner_returns_error_when_no_result_frame(
    datensatz: GeneralisierterDatensatz,
) -> None:
    page = FakePage(frame_body="Irgendwas anderes", url="https://example.de/start")
    portal = DummyPortal()

    result = run_with_page(portal, datensatz, page, RunConfig(verbose=False))

    assert result.status == "error"
    assert result.error_code == "result_frame_not_found"


def test_runner_returns_error_when_fill_form_raises(
    datensatz: GeneralisierterDatensatz,
) -> None:
    class FailingPortal(DummyPortal):
        def fill_form(self, page: Any, d: GeneralisierterDatensatz, cfg: RunConfig) -> None:
            raise RuntimeError("simuliert: Selektor nicht gefunden")

    page = FakePage(url="https://example.de/start")
    portal = FailingPortal()

    result = run_with_page(portal, datensatz, page, RunConfig(verbose=False))

    assert result.status == "error"
    assert result.error_code == "fill_form_failed"
    assert "simuliert" in (result.error_message or "")


def test_portal_base_fill_form_is_abstract() -> None:
    class IncompletePortal(PortalBase):
        NAME = "incomplete"
        START_URL = "https://x"
        COOKIE_ACCEPT_CANDIDATES: list[str] = []
        COOKIE_WRAPPER = ""
        SUBMIT_SELECTOR = ""
        RESULT_FRAME_MARKER = ""

    portal = IncompletePortal()
    with pytest.raises(NotImplementedError):
        portal.fill_form(None, None, None)  # type: ignore[arg-type]


def test_run_result_to_dict_emits_schema_fields(
    datensatz: GeneralisierterDatensatz,
) -> None:
    result = RunResult(
        status="ok",
        portal="dummy",
        marktwert_eur_min=100_000,
        marktwert_eur_max=110_000,
        marktwert_eur_mittel=105_000,
        trends={"jahre_3": 1.0, "jahr_1": 0.5, "prognose": 0.3},
        trend_ampel="gelb",
        trend_ampel_label="stagnierend",
        trend_label="Trend stagnierend",
        url="https://x",
        timestamp="2026-05-15T10:00:00+02:00",
        screenshot_path=None,
    )
    d = result.to_dict()
    assert d["status"] == "ok"
    assert d["portal"] == "dummy"
    assert d["marktwert_eur_mittel"] == 105_000
    assert d["trends"]["jahre_3"] == 1.0
    assert d["trend_ampel"] == "gelb"
    assert "timestamp" in d
