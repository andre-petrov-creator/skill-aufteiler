"""Abstract base for an escalation stage and the result it returns."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScrapeResult:
    html: str
    final_url: str
    stage_name: str
    duration_s: float
    error: Optional[str] = None


class ScraperStage(ABC):
    """One attempt at fetching the expose page.

    Implementations must return a ScrapeResult. They do NOT decide whether the
    result is blocked — that's the orchestrator's job via BlockDetector.
    """

    name: str = "base"
    default_timeout_s: float = 60.0

    @abstractmethod
    def scrape(self, url: str) -> ScrapeResult:
        """Fetch the URL and return rendered HTML + final URL."""
        raise NotImplementedError
