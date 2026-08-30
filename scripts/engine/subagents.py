"""Subagent delivery provider for tests/automation.

In production, subagents are created by the main agent, not by the engine. The
engine emits a task brief and waits for a delivery. A FakeSubagentBackend is used
only in tests and CLI smoke runs to automate that step.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .models import Brief, Delivery


class SubagentBackend(Protocol):
    name: str

    def can_run(self, role: str) -> bool:
        ...

    def dispatch(self, task_id: str, role: str, brief: Brief) -> Delivery:
        ...


class FakeSubagentBackend:
    """Deterministic fake backend for tests and dry runs.

    It writes a minimal valid delivery.json/delivery.md into the task workspace and
    returns a Delivery object. This lets the engine loop be tested without a real
    harness.
    """

    name = "fake"

    def can_run(self, role: str) -> bool:
        return True

    def dispatch(self, task_id: str, role: str, brief: Brief) -> Delivery:
        workspace = brief.workspace
        workspace.mkdir(parents=True, exist_ok=True)
        payload = self._payload_for(role, brief)
        if isinstance(payload, dict):
            payload.setdefault("lessons", [
                {
                    "category": "workflow",
                    "summary": f"Fake {role} workflow lesson.",
                    "detail": "Used by fake backend to verify experience import in smoke tests.",
                }
            ])
        if role == "experiment-runner" and isinstance(payload, dict):
            artifact_path = workspace / "raw_scores.json"
            artifact_path.write_text(json.dumps({"fake_scores": [1, 2, 3]}), encoding="utf-8")
            payload.setdefault("raw_results", []).append(
                {"path": "raw_scores.json", "sha256": None, "kind": "scores"}
            )
            tool_runs = payload.setdefault("tool_runs", [])
            if tool_runs:
                tool_runs[0].setdefault("raw_results", []).append("raw_scores.json")
        delivery_md = (
            f"# {role} delivery\n\n"
            f"Task: {task_id}\n\n"
            "1. What I reviewed: fake test context.\n"
            "2. My main findings: deterministic fake delivery.\n"
            "3. Concrete changes: none.\n"
            "4. Expected impact: enables engine tests.\n"
            "5. Residual risks: not a real scientific delivery.\n"
        )
        delivery_json = {
            "role": role,
            "task_id": task_id,
            "status": "submitted",
            "payload": payload,
        }
        json_path = workspace / "delivery.json"
        md_path = workspace / "delivery.md"
        json_path.write_text(json.dumps(delivery_json, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(delivery_md, encoding="utf-8")
        return Delivery(
            task_id=task_id,
            role=role,
            status="submitted",
            payload=payload,
            delivery_md=delivery_md,
            delivery_json_path=json_path,
        )

    @staticmethod
    def _payload_for(role: str, brief: Brief) -> dict[str, Any]:
        if role == "investigator":
            return {
                "hypothesis_id": "HYP-TBD",
                "operation": "create",
                "claim": "A fake falsifiable chemical claim.",
                "status": "active",
                "assessment": "unassessed",
                "predictions": ["Prediction A"],
                "falsifiers": ["Outcome that would refute"],
                "scope": ["test scope"],
                "change_summary": "created by fake backend",
            }
        if role == "challenger":
            return {
                "target_ids": ["HYP-001"],
                "faithful_restatement": "A fake restatement.",
                "readiness": "ready-for-test-design",
                "issues": [],
                "alternatives": [],
                "falsifying_outcomes": [],
                "recommended_tests": [],
            }
        if role == "test-designer":
            return {
                "target_hypothesis_ids": ["HYP-001"],
                "research_move": "contrast",
                "evidence_grade": "screening",
                "law_quality_gap": "controlled_discrimination",
                "scientific_decision": "Choose between the competing fake mechanisms.",
                "predictions_to_test": ["Prediction A"],
                "method": "fake method",
                "inputs": ["input"],
                "controls": ["control"],
                "decision_criteria": ["criterion"],
                "failure_criteria": ["failure"],
                "capabilities": ["rdkit"],
                "frozen": False,
            }
        if role == "experiment-runner":
            return {
                "frozen_test_plan_ref": "TST-001",
                "tool_runs": [
                    {
                        "tool_name": "fake",
                        "command": "python -m fake",
                        "status": "succeeded",
                        "exit_code": 0,
                        "raw_results": [],
                        "wall_seconds": 0.0,
                    }
                ],
                "deviations": [],
                "raw_results": [],
            }
        if role == "result-analyst":
            return {
                "statistics": [],
                "observations": [{"text": "Fake observation.", "source_refs": []}],
                "evidence_candidates": [
                    {
                        "evidence_id": "EVD-TBD",
                        "hypothesis_id": "HYP-001",
                        "direction": "support",
                        "narrative": "Fake candidate.",
                    }
                ],
            }
        if role == "evidence-reviewer":
            return {
                "independence_declaration": "independent",
                "reviews": [
                    {
                        "evidence_id": "EVD-TBD",
                        "verdict": "accepted",
                        "reasons": "Fake review.",
                        "permitted_scope": "test scope",
                        "required_work": None,
                    }
                ],
            }
        if role == "mission-synthesizer":
            return {
                "mission_verdict": "inconclusive",
                "law_quality_ledger": {
                    "law_candidate": "fake law candidate",
                    "maturity": "lead",
                    "criteria": {
                        "mechanism": "partial",
                        "controlled_discrimination": "partial",
                        "generality": "partial",
                        "boundary_map": "partial",
                        "decision_utility": "partial",
                        "reproducibility": "not_applicable",
                    },
                    "gaps": ["fake decisive control"],
                },
                "research_frontier": [
                    {
                        "move": "contrast",
                        "target_law_candidate": "fake law candidate",
                        "quality_gap": "controlled_discrimination",
                        "expected_decision_change": "Select the surviving mechanism.",
                        "evidence_grade": "discrimination",
                        "priority": "medium",
                        "disposition": "rejected_scientific",
                    }
                ],
                "hypothesis_updates": [],
                "evidence_summary": [],
                "unresolved_alternatives": [],
                "open_questions": [],
                "capability_notes": [],
                "contribution_to_research": "fake contribution",
                "recommended_next_direction": "none",
            }
        return {"note": f"fake delivery for {role}"}

