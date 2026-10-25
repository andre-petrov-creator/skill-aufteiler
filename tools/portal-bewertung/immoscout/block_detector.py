"""Detect whether a fetched page is an Imperva block instead of the real expose."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class BlockDecision:
    blocked: bool
    markers: List[str] = field(default_factory=list)


class BlockDetector:
    """Six markers, 2-of-6 rule. Marker names are stable strings for logs."""

    MIN_BODY_LEN = 2000

    def evaluate(self, *, html: str, status_code: int, headers: Dict[str, str], final_url: str) -> BlockDecision:
        markers: List[str] = []

        lowered = html.lower()
        if "ich bin kein roboter" in lowered:
            markers.append("imperva_text")
        if "_incapsula_resource" in lowered or "incapsula" in final_url.lower():
            markers.append("incapsula_url")
        if status_code in (403, 429):
            markers.append("http_4xx")
        if any(k.lower() == "x-iinfo" for k in headers):
            markers.append("xinfo_header")
        if len(html) < self.MIN_BODY_LEN:
            markers.append("short_body")
        if "keyvalues" not in lowered:
            markers.append("no_keyvalues")

        return BlockDecision(blocked=len(markers) >= 2, markers=markers)
