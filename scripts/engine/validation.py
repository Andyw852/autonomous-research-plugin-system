"""Delivery and gate validation.

The engine uses these checks as deterministic protocol gates. Scientific judgement
remains in the subagents; this module only checks structure, integrity, and role
boundaries.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import Delivery, Task

# Minimum required payload keys per role. This is intentionally structural; the
# original role prompts remain the authority for scientific content.
ROLE_REQUIRED_PAYLOAD: dict[str, set[str]] = {
    "investigator": {"operation", "claim"},
    "challenger": {"target_ids", "readiness", "issues"},
    "test-designer": {
        "research_move", "evidence_grade", "law_quality_gap", "scientific_decision",
        "method", "inputs", "decision_criteria", "capabilities",
    },
    "experiment-runner": {"frozen_test_plan_ref", "tool_runs", "deviations", "raw_results"},
    "result-analyst": {"statistics", "observations", "evidence_candidates"},
    "evidence-reviewer": {"independence_declaration", "reviews"},
    "mission-synthesizer": {
        "mission_verdict",
        "law_quality_ledger",
        "research_frontier",
        "hypothesis_updates",
        "evidence_summary",
        "unresolved_alternatives",
        "open_questions",
        "contribution_to_research",
    },
}


def validate_delivery(task: Task, delivery: Delivery) -> list[str]:
    errors: list[str] = []
    if task.role != delivery.role:
        errors.append(f"task role {task.role} does not match delivery role {delivery.role}")
    if delivery.status != "submitted":
        errors.append(f"delivery status is {delivery.status!r}, expected 'submitted'")
    if not delivery.delivery_md.strip():
        errors.append("delivery.md is empty")
    if not delivery.delivery_json_path.is_file():
        errors.append(f"delivery.json missing: {delivery.delivery_json_path}")
    else:
        try:
            data = json.loads(delivery.delivery_json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "payload" not in data:
                errors.append("delivery.json must contain a payload object")
            else:
                payload = data["payload"]
                if isinstance(payload, list):
                    if delivery.role != "investigator":
                        errors.append("only investigator deliveries may use a payload list")
                    else:
                        for i, item in enumerate(payload):
                            if not isinstance(item, dict):
                                errors.append(f"payload[{i}] must be an object")
                            else:
                                missing = {"operation", "claim"} - set(item.keys())
                                if missing:
                                    errors.append(
                                        f"investigator payload[{i}] missing fields: {sorted(missing)}"
                                    )
                elif isinstance(payload, dict):
                    required = ROLE_REQUIRED_PAYLOAD.get(delivery.role, set())
                    missing = required - set(payload.keys())
                    if missing:
                        errors.append(
                            f"{delivery.role} delivery missing payload fields: {sorted(missing)}"
                        )
                else:
                    errors.append("delivery.json payload must be an object or investigator list")
        except json.JSONDecodeError as exc:
            errors.append(f"delivery.json is not valid JSON: {exc}")
    if "1. what" not in delivery.delivery_md.lower() and "what i" not in delivery.delivery_md.lower():
        # The exact section headings vary; require at least some narrative length.
        if len(delivery.delivery_md.strip()) < 80:
            errors.append("delivery.md is too short to be a meaningful narrative")
    return errors


def validate_delivery_context(
    task: Task,
    delivery: Delivery,
    timeline: list[dict[str, Any]],
) -> list[str]:
    """Gate checks that depend on the current timeline state."""
    errors: list[str] = []
    mission_events = [e for e in timeline if e.get("mission_id") == task.mission_id]
    types = [e.get("type") for e in mission_events]

    if task.role == "experiment-runner" and "test_plan" not in types:
        errors.append("experiment-runner delivery requires a frozen test_plan event first")
    if task.role == "result-analyst" and "tool_run" not in types:
        errors.append("result-analyst delivery requires at least one tool_run event first")
    if task.role == "evidence-reviewer" and "evidence_candidate" not in types:
        errors.append("evidence-reviewer delivery requires at least one evidence_candidate event first")
    if task.role == "mission-synthesizer" and "review" not in types:
        errors.append("mission-synthesizer delivery requires at least one review event first")
    return errors


def validate_artifact_hashes(delivery: Delivery, run_root: Path) -> list[str]:
    """Check artifact paths referenced by the delivery exist and match sha256 where given."""
    errors: list[str] = []
    payload = delivery.payload
    if not isinstance(payload, dict):
        return errors
    refs: list[dict[str, Any]] = []
    refs.extend(payload.get("raw_results") or [])
    for run in payload.get("tool_runs") or []:
        refs.extend(run.get("raw_results") or [])
        refs.extend(run.get("artifacts") or [])
    for ref in refs:
        if isinstance(ref, str):
            path = run_root / ref
            if not path.is_file():
                errors.append(f"artifact not found: {ref}")
        elif isinstance(ref, dict):
            rel = ref.get("path") or ref.get("file")
            if rel:
                path = run_root / rel
                if not path.is_file():
                    errors.append(f"artifact not found: {rel}")
                elif ref.get("sha256"):
                    actual = _sha256(path)
                    if actual != ref["sha256"]:
                        errors.append(f"sha256 mismatch for {rel}")
    return errors


def validate_frozen_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("frozen") is not True:
        errors.append("test plan is not frozen")
    return errors


def validate_review_independence(
    timeline: list[dict[str, Any]],
    evidence_candidate_event_id: str,
    reviewer_role: str,
    hypothesis_author_role: str | None,
) -> list[str]:
    errors: list[str] = []
    if hypothesis_author_role and hypothesis_author_role == reviewer_role:
        errors.append("hypothesis author cannot review their own evidence")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
