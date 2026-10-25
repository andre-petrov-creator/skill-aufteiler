"""Escalation loop: walk stages until one returns a non-blocked result."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .block_detector import BlockDetector
from .stages.base import ScraperStage, ScrapeResult


@dataclass
class StageAttempt:
    name: str
    duration_s: float
    blocked: bool
    markers: List[str]
    error: Optional[str]


@dataclass
class OrchestratorResult:
    success: bool
    result: Optional[ScrapeResult]
    successful_stage: Optional[str]
    stages_attempted: List[str] = field(default_factory=list)
    attempts: List[StageAttempt] = field(default_factory=list)


class Orchestrator:
    """Run stages in order until one passes the BlockDetector."""

    def __init__(self, stages: Sequence[ScraperStage], detector: Optional[BlockDetector] = None, inter_stage_pause_s: float = 8.0) -> None:
        self.stages = list(stages)
        self.detector = detector or BlockDetector()
        self.inter_stage_pause_s = inter_stage_pause_s

    def run(self, url: str) -> OrchestratorResult:
        attempts: List[StageAttempt] = []

        for idx, stage in enumerate(self.stages):
            scrape = stage.scrape(url)
            decision = self.detector.evaluate(
                html=scrape.html,
                status_code=200,  # stages don't expose status — keep simple
                headers={},
                final_url=scrape.final_url,
            )
            attempts.append(StageAttempt(
                name=stage.name,
                duration_s=scrape.duration_s,
                blocked=decision.blocked,
                markers=decision.markers,
                error=scrape.error,
            ))
            if not decision.blocked and scrape.error is None:
                return OrchestratorResult(
                    success=True,
                    result=scrape,
                    successful_stage=stage.name,
                    stages_attempted=[a.name for a in attempts],
                    attempts=attempts,
                )
            # if not last, pause
            if idx < len(self.stages) - 1:
                time.sleep(self.inter_stage_pause_s)

        return OrchestratorResult(
            success=False,
            result=None,
            successful_stage=None,
            stages_attempted=[a.name for a in attempts],
            attempts=attempts,
        )
