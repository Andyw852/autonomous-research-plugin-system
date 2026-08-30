"""Inner-loop flow definition.

The deterministic engine uses this table to know which role belongs to each phase.
Multi-round looping and condition routing are implemented in ProtocolEngine.
"""
from __future__ import annotations

# Inner-loop phases. "engine" means a deterministic gate, not a subagent role.
INNER_LOOP_PHASES = [
    {"id": "hypothesize", "role": "investigator"},
    {"id": "challenge", "role": "challenger"},
    {"id": "revise", "role": "investigator"},
    {"id": "design", "role": "test-designer"},
    {"id": "freeze", "role": "engine"},
    {"id": "execute", "role": "experiment-runner"},
    {"id": "analyze", "role": "result-analyst"},
    {"id": "review", "role": "evidence-reviewer"},
    {"id": "decide", "role": "engine"},
    {"id": "commit", "role": "engine"},
]


def phase_role(phase_id: str) -> str:
    for phase in INNER_LOOP_PHASES:
        if phase["id"] == phase_id:
            return phase["role"]
    raise KeyError(f"unknown inner phase: {phase_id}")
