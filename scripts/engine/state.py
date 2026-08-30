"""State reconstruction from the blackboard logs.

The engine never trusts session memory. It rebuilds the campaign/mission state from
timeline.jsonl and traces.jsonl on every invocation.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from .blackboard import Blackboard


@dataclasses.dataclass
class ResearchState:
    campaign: dict[str, Any]
    missions: dict[str, Any]
    hypotheses: dict[str, Any]
    evidence: dict[str, Any]
    decisions: list[dict[str, Any]]
    mission_reports: list[dict[str, Any]]
    tasks: dict[str, Any]
    timeline: list[dict[str, Any]]
    traces: list[dict[str, Any]]
    last_mission_id: str | None

    @classmethod
    def load(cls, blackboard: Blackboard) -> "ResearchState":
        model = blackboard.build_model()
        return cls(
            campaign=model.get("campaign", {}),
            missions=model.get("missions", {}),
            hypotheses=model.get("hypotheses", {}),
            evidence=model.get("evidence", {}),
            decisions=model.get("decisions", []),
            mission_reports=model.get("mission_reports", []),
            tasks=model.get("tasks", {}),
            timeline=model.get("timeline", []),
            traces=model.get("traces", []),
            last_mission_id=model.get("last_mission_id"),
        )
