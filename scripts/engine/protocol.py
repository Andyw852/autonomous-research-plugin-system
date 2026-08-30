"""Deterministic ProtocolEngine.

The engine owns protocol mechanics. It does not produce scientific content; it
schedules subagent tasks, validates deliveries, appends events/traces, and advances
the flow based on explicit state.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import traces as trace_helpers
from .blackboard import Blackboard
from .config import PluginConfig, load_config
from .experience import relevant_entries
from .flows import phase_role
from .models import Brief, Delivery, Task
from .state import ResearchState
from .subagents import FakeSubagentBackend
from .validation import (
    validate_artifact_hashes,
    validate_delivery,
    validate_delivery_context,
    validate_frozen_plan,
)


LAW_MATURITY = {"lead", "rule_candidate", "rule", "law"}
LAW_CRITERIA = (
    "mechanism",
    "controlled_discrimination",
    "generality",
    "boundary_map",
    "decision_utility",
    "reproducibility",
)
LAW_CRITERION_OK = {"pass", "not_applicable"}


class ProtocolEngine:
    def __init__(self, config: PluginConfig | None = None, backend=None, blackboard: Blackboard | None = None):
        self.config = config or load_config()
        self.bb = blackboard or Blackboard(self.config.run_root, self.config.blackboard_scripts_dir)
        # In production, subagents are created by the main agent. `backend` is only
        # used for tests/automation (e.g. FakeSubagentBackend).
        if backend is not None:
            self.backend = backend
        elif self.config.subagent_backend == "fake":
            self.backend = FakeSubagentBackend()
        else:
            self.backend = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start_campaign(self, objective: str) -> dict[str, Any]:
        # Always isolate each new Campaign in its own folder under the configured run root.
        base = self.bb.run_root
        campaign_id = self.bb.events.new_id("CAM")
        self.bb.run_root = base / campaign_id
        self.bb.run_root.mkdir(parents=True, exist_ok=True)
        self.bb.snapshot_config(
            {
                "config_version": getattr(self.config, "config_version", "0.1.0"),
                "campaign": {
                    "max_outer_rounds": self.config.max_outer_rounds,
                    "max_tokens_per_round": 0,
                    "network_policy": self.config.network_policy,
                    "risk_level": "routine",
                    "language": self.config.language,
                },
                "mission": {
                    "max_inner_rounds": self.config.max_inner_rounds,
                    "min_hypotheses": self.config.min_hypotheses,
                    "max_hypotheses": self.config.max_hypotheses,
                },
                "director": {
                    "propose_count": self.config.propose_count,
                    "min_outer_rounds": self.config.min_outer_rounds,
                    "closure_mode": self.config.closure_mode,
                },
            }
        )
        event_id, line = self.bb.append_timeline(
            {
                "type": "campaign_init",
                "role": "orchestrator",
                "status": "active",
                "summary": "Campaign initialized for autonomous research.",
                "content": {
                    "campaign_id": self.bb.run_root.name,
                    "objective": objective,
                    "status": "active",
                },
            }
        )
        if self.config.auto_rebuild == "after_each_event":
            self.bb.render()
        return {"event_id": event_id, "line": line}

    def build_snapshot(self) -> ResearchState:
        return ResearchState.load(self.bb)

    def validate(self) -> list[str]:
        return self.bb.validate()

    def round_status(self) -> dict[str, Any]:
        """Return a concise outer-loop status report for the Director/main agent."""
        state = self.build_snapshot()
        latest_report = state.mission_reports[-1] if state.mission_reports else None
        reported_missions = {r.get("mission_id") for r in state.mission_reports}
        incomplete_missions = sorted(
            mid for mid in state.missions if mid not in reported_missions
        )
        ended_tasks = {e.get("task_id") for e in state.traces if e.get("kind") == "task_end"}
        pending_tasks = sorted(set(state.tasks) - ended_tasks)
        readiness = self._closure_readiness()
        return {
            "campaign": state.campaign,
            "active_mission_count": len(state.missions),
            "hypothesis_count": len(state.hypotheses),
            "accepted_evidence_count": sum(
                1 for ev in state.evidence.values() if ev.get("verdict") == "accepted"
            ),
            "latest_mission_report": latest_report,
            "incomplete_missions": incomplete_missions,
            "pending_tasks": pending_tasks,
            "closure_readiness": readiness,
            "remaining_outer_rounds": max(
                0, self.config.max_outer_rounds - len(state.mission_reports)
            ),
        }

    def _closure_readiness(self) -> dict[str, Any]:
        """Compute whether the Campaign is eligible for scientific_closure."""
        state = self.build_snapshot()
        reported_missions = {r.get("mission_id") for r in state.mission_reports}
        incomplete_missions = sorted(
            mid for mid in state.missions if mid not in reported_missions
        )
        ended_tasks = {e.get("task_id") for e in state.traces if e.get("kind") == "task_end"}
        pending_tasks = sorted(set(state.tasks) - ended_tasks)
        pending_open: list[str] = []
        pending_boundary: list[str] = []
        pending_frontier: list[str] = []
        frontier_final = {
            "accepted_for_mission", "rejected_scientific", "out_of_scope", "user_override",
        }
        for report in state.mission_reports:
            content = report.get("content") or {}
            for q in content.get("open_questions") or []:
                if isinstance(q, dict):
                    status = q.get("status")
                    if status not in {"resolved", "out_of_scope", "deferred"}:
                        pending_open.append(str(q.get("question") or q))
                else:
                    pending_open.append(str(q))
            for cand in content.get("boundary_extension_candidates") or []:
                if isinstance(cand, str):
                    pending_boundary.append(cand)
                    continue
                if not isinstance(cand, dict):
                    continue
                disposition = cand.get("disposition", "pending")
                feasibility = cand.get("feasibility", "uncertain")
                if disposition not in {
                    "accepted_for_mission", "rejected_scientific", "user_override",
                } and feasibility != "infeasible":
                    pending_boundary.append(str(cand.get("candidate") or cand))
        latest_report = state.mission_reports[-1] if state.mission_reports else None
        latest_content = latest_report.get("content") if latest_report else {}
        for item in (latest_content or {}).get("research_frontier") or []:
            if not isinstance(item, dict):
                continue
            priority = item.get("priority", "medium")
            disposition = item.get("disposition", "pending")
            if priority in {"high", "medium"} and disposition not in frontier_final:
                label = (
                    item.get("target_law_candidate")
                    or item.get("quality_gap")
                    or item
                )
                pending_frontier.append(str(label))
        outer_completed = len(state.mission_reports)
        min_outer_met = outer_completed >= self.config.min_outer_rounds
        boundary_resolved = (
            not pending_boundary
            if self.config.require_boundary_extension_resolution
            else True
        )
        eligible = (
            not incomplete_missions
            and not pending_tasks
            and min_outer_met
            and boundary_resolved
        )
        return {
            "incomplete_missions": incomplete_missions,
            "pending_tasks": pending_tasks,
            "open_questions_pending_disposition": pending_open,
            "pending_boundary_extensions": pending_boundary,
            "pending_research_frontier": pending_frontier,
            "boundary_extensions_resolved": boundary_resolved,
            "outer_rounds_completed": outer_completed,
            "min_outer_rounds": self.config.min_outer_rounds,
            "min_outer_met": min_outer_met,
            "eligible_for_closure": eligible,
        }

    # ------------------------------------------------------------------
    # Directives / Mission lifecycle
    # ------------------------------------------------------------------
    def consume_directives(self, round_number: int | None = None) -> list[dict[str, Any]]:
        """Scan blackboard/directives/round-* for unconsumed proposal/review/decision files.

        Each file is marked consumed independently so a round can contain a
        proposal, a direction review, and a later decision.
        """
        consumed_events: list[dict[str, Any]] = []
        directives_root = self.bb.run_root / "blackboard" / "directives"
        if not directives_root.is_dir():
            return consumed_events
        rounds = sorted(
            d for d in directives_root.iterdir()
            if d.is_dir() and d.name.startswith("round-")
        )
        for round_dir in rounds:
            proposal = round_dir / "proposal.json"
            decision = round_dir / "decision.json"
            if proposal.is_file() and not (round_dir / "proposal.consumed.json").exists():
                data = json.loads(proposal.read_text(encoding="utf-8"))
                event_id, _ = self.bb.append_timeline(
                    {
                        "type": "mission_proposal",
                        "role": "director",
                        "status": "proposed",
                        "summary": data.get("summary", "Director proposed a Mission."),
                        "content": {
                            "research_question": data.get("research_question", ""),
                            "expected_knowledge_gain": data.get("expected_knowledge_gain", ""),
                            "hypothesis_directions": data.get("hypothesis_directions", []),
                            "scope": data.get("scope", []),
                            "non_goals": data.get("non_goals", []),
                            "success_criteria": data.get("success_criteria", {}),
                            "available_capabilities": data.get("available_capabilities", []),
                            "boundary_extension_targets": data.get("boundary_extension_targets", []),
                            "affected_hypotheses": data.get("affected_hypotheses", []),
                            "narrowing_rationale": data.get("narrowing_rationale", ""),
                            "exit_conditions": data.get("exit_conditions", {}),
                        },
                    }
                )
                self._mark_consumed(round_dir, "proposal", {"event_id": event_id})
                consumed_events.append({"kind": "proposal", "round": round_dir.name, "event_id": event_id})
            direction_review = round_dir / "direction_review.json"
            if direction_review.is_file() and not (round_dir / "direction_review.consumed.json").exists():
                data = json.loads(direction_review.read_text(encoding="utf-8"))
                event_id, _ = self.bb.append_timeline(
                    {
                        "type": "direction_review",
                        "role": "direction-reviewer",
                        "status": data.get("verdict", "review"),
                        "summary": data.get("summary", "Direction review recorded."),
                        "content": data,
                    }
                )
                self._mark_consumed(round_dir, "direction_review", {"event_id": event_id})
                consumed_events.append(
                    {"kind": "direction_review", "round": round_dir.name, "event_id": event_id}
                )
            if decision.is_file() and not (round_dir / "decision.consumed.json").exists():
                data = json.loads(decision.read_text(encoding="utf-8"))
                if data.get("recommendation") == "scientific_closure":
                    self._validate_scientific_closure(data)
                event_id, _ = self.bb.append_timeline(
                    {
                        "type": "decision",
                        "role": "director",
                        "status": data.get("recommendation", "decision"),
                        "summary": data.get("summary", "Director recorded a decision."),
                        "content": {
                            "text": data.get("rationale", ""),
                            "rationale": data.get("rationale", ""),
                            "final_law": data.get("final_law"),
                        },
                    }
                )
                self._mark_consumed(round_dir, "decision", {"event_id": event_id})
                consumed_events.append({"kind": "decision", "round": round_dir.name, "event_id": event_id})
            if consumed_events and self.config.auto_rebuild == "after_each_event":
                self.bb.render()
        return consumed_events

    def admit_mission(self, mission_id: str, proposal: dict[str, Any] | None = None) -> dict[str, Any]:
        event_id, line = self.bb.append_timeline(
            {
                "type": "mission_admit",
                "role": "orchestrator",
                "mission_id": mission_id,
                "status": "admitted",
                "summary": f"Mission {mission_id} was admitted.",
                "content": {
                    "research_question": (proposal or {}).get("research_question", ""),
                    "expected_knowledge_gain": (proposal or {}).get("expected_knowledge_gain", ""),
                    "status": "admitted",
                },
            }
        )
        return {"event_id": event_id, "line": line}

    # ------------------------------------------------------------------
    # Tasks / subagents
    # ------------------------------------------------------------------
    def dispatch_task(self, role: str, mission_id: str | None = None, context: dict[str, Any] | None = None) -> Task:
        task_id = self.bb.events.new_id("TSK")
        workspace = self.bb.run_root / "tasks" / task_id / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        full_context = self._build_brief_context(role, mission_id, context or {})
        brief = Brief(
            role=role,
            task_id=task_id,
            mission_id=mission_id,
            content=full_context,
            workspace=workspace,
            context={"mission_id": mission_id},
            experience_entries=relevant_entries(self.bb, role=role),
        )
        task = Task(id=task_id, role=role, mission_id=mission_id, workspace=workspace, brief=brief)
        (workspace / "task.json").write_text(
            json.dumps(
                {"task_id": task_id, "role": role, "mission_id": mission_id},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        trace_helpers.task_start(self.bb, task_id, role)
        trace_helpers.brief_sent(self.bb, task_id, role, {"mission_id": mission_id, "brief": full_context})
        if self.config.auto_rebuild == "after_each_event":
            self.bb.render()
        return task

    def _build_brief_context(self, role: str, mission_id: str | None, context: dict[str, Any]) -> dict[str, Any]:
        """Assemble a useful blackboard context for a subagent brief."""
        state = self.build_snapshot()
        mission = state.missions.get(mission_id or "", {}) if mission_id else {}
        hypotheses = [
            {
                "id": h.get("id"),
                "claim": h.get("claim"),
                "assessment": h.get("assessment"),
                "status": h.get("status"),
            }
            for h in state.hypotheses.values()
        ]
        context.setdefault("mission_id", mission_id)
        context.setdefault("research_question", mission.get("question", ""))
        context.setdefault("hypotheses", hypotheses)
        context.setdefault("evidence", [
            {"id": e.get("id"), "hypothesis_id": e.get("hypothesis_id"), "verdict": e.get("verdict")}
            for e in state.evidence.values()
        ])
        if role == "experiment-runner":
            frozen = self._latest_frozen_test_plan(mission_id)
            if frozen:
                context.setdefault("frozen_test_plan", frozen.get("content", {}))
        return context

    @staticmethod
    def _hypothesis_count(payload: Any) -> int:
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            if "hypotheses" in payload:
                return len(payload["hypotheses"])
            return 1 if any(k in payload for k in ("hypothesis_id", "claim", "operation")) else 0
        return 0

    def receive_delivery(self, task: Task, delivery: Delivery) -> list[dict[str, Any]]:
        self._stage_delivery_artifacts(task, delivery)
        errors = validate_delivery(task, delivery)
        errors += validate_delivery_context(task, delivery, self.bb.read_timeline())
        errors += validate_artifact_hashes(delivery, self.bb.run_root)
        if task.role == "investigator":
            count = self._hypothesis_count(delivery.payload)
            if count < self.config.min_hypotheses or count > self.config.max_hypotheses:
                errors.append(
                    f"investigator delivered {count} hypotheses; expected "
                    f"{self.config.min_hypotheses}-{self.config.max_hypotheses}"
                )
        if errors:
            raise ValueError("; ".join(errors))
        task.delivery = delivery
        task.status = "delivered"
        trace_helpers.delivery_received(self.bb, task.id, task.role)
        if delivery.progress_path and delivery.progress_path.is_file():
            self.bb.import_progress(task.id, task.role, delivery.progress_path.parent)
        lessons = delivery.lessons
        if not lessons and isinstance(delivery.payload, dict):
            lessons = delivery.payload.get("lessons", [])
        if lessons:
            self.bb.experience_import(delivery.delivery_json_path, task.role, task.id)
        events = self._append_delivery_events(task, delivery)
        trace_helpers.task_end(self.bb, task.id, task.role)
        if self.config.auto_rebuild == "after_each_event":
            self.bb.render()
        return events

    # ------------------------------------------------------------------
    # Artifact preservation
    # ------------------------------------------------------------------
    def _stage_delivery_artifacts(self, task: Task, delivery: Delivery) -> None:
        """Copy any artifact files referenced by a delivery into run_root/artifacts/.

        This preserves each round's computed substances, scores, and raw results
        in a stable campaign-level artifacts directory.
        """
        payload = delivery.payload
        if not isinstance(payload, dict):
            return
        raw_results = payload.get("raw_results")
        if isinstance(raw_results, list):
            for i, item in enumerate(raw_results):
                raw_results[i] = self._stage_artifact_ref(task, item)
        for run in payload.get("tool_runs") or []:
            if not isinstance(run, dict):
                continue
            for key in ("raw_results", "artifacts"):
                refs = run.get(key)
                if isinstance(refs, list):
                    for i, ref in enumerate(refs):
                        refs[i] = self._stage_artifact_ref(task, ref)

    def _stage_artifact_ref(self, task: Task, ref: Any) -> Any:
        if isinstance(ref, str):
            return self._stage_artifact_file(task, ref)
        if isinstance(ref, dict):
            old = ref.get("path") or ref.get("file")
            if old:
                new_path = self._stage_artifact_file(task, old)
                ref["path"] = new_path
                ref["file"] = new_path
                dest = self.bb.run_root / new_path
                if dest.is_file():
                    ref["sha256"] = self.bb.events.sha256_file(dest)
            return ref
        return ref

    def _stage_artifact_file(self, task: Task, rel: str) -> str:
        if not rel:
            return rel
        candidates = [task.workspace / rel, self.bb.run_root / rel]
        source = next((p for p in candidates if p.is_file()), None)
        if source is None:
            return rel
        source = source.resolve()
        artifacts_root = (self.bb.run_root / "artifacts").resolve()
        if str(source).startswith(str(artifacts_root)):
            return rel
        if task.workspace.resolve() in source.parents:
            sub = source.relative_to(task.workspace.resolve())
        else:
            sub = Path(source.name)
        dest = artifacts_root / (task.mission_id or "no-mission") / task.id / sub
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        return dest.relative_to(self.bb.run_root).as_posix()

    # ------------------------------------------------------------------
    # Inner loop
    # ------------------------------------------------------------------
    def advance(self, mission_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Advance one deterministic protocol step for a Mission."""
        phase = self._infer_inner_phase(mission_id)
        if phase is None:
            return {"status": "complete", "mission_id": mission_id, "phase": None}

        if phase == "synthesize":
            result = self.synthesize_mission(mission_id, context or {})
            return {"status": "synthesized", "mission_id": mission_id, "phase": phase, **result}

        if phase in {"freeze", "decide", "commit"}:
            result = self._run_engine_gate(phase, mission_id)
            return {"status": "gate", "mission_id": mission_id, "phase": phase, **result}

        role = phase_role(phase)
        task = self.dispatch_task(role, mission_id, context or {})
        if self.backend is None:
            return {
                "status": "awaiting_subagent",
                "mission_id": mission_id,
                "phase": phase,
                "role": role,
                "task_id": task.id,
                "workspace": str(task.workspace),
                "brief": task.brief.content,
            }
        delivery = self.backend.dispatch(task.id, role, task.brief)
        events = self.receive_delivery(task, delivery)
        return {
            "status": "dispatched",
            "mission_id": mission_id,
            "phase": phase,
            "role": role,
            "task_id": task.id,
            "events": events,
        }

    def _infer_inner_phase(self, mission_id: str) -> str | None:
        timeline = self.bb.read_timeline()
        mission_events = [e for e in timeline if e.get("mission_id") == mission_id]
        types = [e.get("type") for e in mission_events]

        def has(t: str) -> bool:
            return t in types

        # After all inner rounds, synthesis is the final step.
        if has("mission_report"):
            return None

        completed_rounds = self._inner_round_count(mission_events)
        committed = [
            e for e in mission_events
            if e.get("type") == "decision" and e.get("status") == "committed"
        ]
        last_committed = committed[-1] if committed else None

        if last_committed is not None:
            # Current round = events written after the last committed round.
            current_events = [
                e for e in mission_events
                if e.get("created_at", "") > last_committed.get("created_at", "")
            ]
            if not current_events:
                if completed_rounds >= self.config.max_inner_rounds:
                    return "synthesize"
                return "hypothesize"
            round_events = current_events
        else:
            round_events = mission_events

        round_types = [e.get("type") for e in round_events]

        def has_round(t: str) -> bool:
            return t in round_types

        if not has_round("hypothesis"):
            return "hypothesize"
        if not has_round("challenge"):
            return "challenge"

        challenges = [e for e in round_events if e.get("type") == "challenge"]
        if challenges:
            last_challenge = challenges[-1]
            readiness = (last_challenge.get("content") or {}).get("readiness")
            hypothesis_after = any(
                e.get("type") == "hypothesis" and e.get("created_at", "") > last_challenge.get("created_at", "")
                for e in round_events
            )
            if readiness == "needs-hypothesis-revision" and not hypothesis_after:
                return "revise"

        if not has_round("test_plan"):
            return "design"
        if not self._latest_frozen_test_plan(mission_id):
            return "freeze"
        if not has_round("tool_run"):
            return "execute"
        if not has_round("observation") and not has_round("evidence_candidate"):
            return "analyze"
        if not has_round("review"):
            return "review"

        decisions = [e for e in round_events if e.get("type") == "decision"]
        if not decisions:
            return "decide"
        committed_in_round = [e for e in decisions if e.get("status") == "committed"]
        if not committed_in_round:
            return "commit"
        # Should not normally be reached because a commit starts a new round above.
        return "synthesize"

    @staticmethod
    def _inner_round_count(mission_events: list[dict[str, Any]]) -> int:
        return sum(
            1 for e in mission_events
            if e.get("type") == "decision" and e.get("status") == "committed"
        )

    def _latest_frozen_test_plan(self, mission_id: str | None) -> dict[str, Any] | None:
        if not mission_id:
            return None
        plans = [
            e for e in self.bb.read_timeline()
            if e.get("mission_id") == mission_id and e.get("type") == "test_plan"
            and (e.get("content") or {}).get("frozen") is True
        ]
        if not plans:
            return None
        return plans[-1]

    def _run_engine_gate(self, phase: str, mission_id: str) -> dict[str, Any]:
        if phase == "freeze":
            return self._freeze_test_plan(mission_id)
        if phase == "decide":
            event_id, _ = self.bb.append_timeline(
                {
                    "type": "decision",
                    "role": "orchestrator",
                    "mission_id": mission_id,
                    "status": "round_decided",
                    "summary": f"Mission {mission_id} round decision recorded.",
                    "content": {"text": "Round decision", "rationale": "Deterministic engine gate."},
                }
            )
            return {"action": "decide", "event_id": event_id}
        if phase == "commit":
            event_id, _ = self.bb.append_timeline(
                {
                    "type": "decision",
                    "role": "orchestrator",
                    "mission_id": mission_id,
                    "status": "committed",
                    "summary": f"Mission {mission_id} round committed.",
                    "content": {"text": "Committed", "rationale": "Deterministic engine gate."},
                }
            )
            self.bb.checkpoint()
            return {"action": "commit", "event_id": event_id}
        raise ValueError(f"unknown engine gate: {phase}")

    def _freeze_test_plan(self, mission_id: str) -> dict[str, Any]:
        plans = [
            e for e in self.bb.read_timeline()
            if e.get("mission_id") == mission_id and e.get("type") == "test_plan"
        ]
        if not plans:
            raise ValueError("cannot freeze: no test_plan exists")
        latest = plans[-1]
        if (latest.get("content") or {}).get("frozen") is True:
            return {"action": "freeze_ok", "event_id": latest.get("id")}
        content = dict(latest.get("content") or {})
        errors = validate_frozen_plan({**content, "frozen": True})
        if errors:
            raise ValueError("; ".join(errors))
        event_id, _ = self.bb.append_timeline(
            {
                "type": "test_plan",
                "role": "orchestrator",
                "mission_id": mission_id,
                "task_id": latest.get("task_id"),
                "summary": f"The test plan for Mission {mission_id} was frozen.",
                "content": {**content, "frozen": True},
                "replies_to": latest.get("id"),
            }
        )
        return {"action": "freeze", "event_id": event_id}

    def synthesize_mission(self, mission_id: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self.dispatch_task("mission-synthesizer", mission_id, context or {})
        if self.backend is None:
            return {
                "status": "awaiting_subagent",
                "task_id": task.id,
                "role": "mission-synthesizer",
                "workspace": str(task.workspace),
                "brief": task.brief.content,
            }
        delivery = self.backend.dispatch(task.id, "mission-synthesizer", task.brief)
        events = self.receive_delivery(task, delivery)
        return {"task_id": task.id, "events": events}

    def run_inner_loop_full(self, mission_id: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Advance the Mission through all inner rounds and synthesis."""
        steps: list[dict[str, Any]] = []
        # Hard safety bound: each round has at most 10 phases, so this is generous.
        max_steps = 20 + self.config.max_inner_rounds * 20
        for _ in range(max_steps):
            result = self.advance(mission_id, context or {})
            steps.append(result)
            if result["status"] == "complete":
                break
        return steps

    # ------------------------------------------------------------------
    # Delivery submission
    # ------------------------------------------------------------------
    def load_task(self, task_id: str) -> Task:
        """Reconstruct a Task from its workspace task.json (fallback to traces)."""
        task_dir = self.bb.run_root / "tasks" / task_id
        workspace = task_dir / "workspace"
        task_json = workspace / "task.json"
        if task_json.is_file():
            data = json.loads(task_json.read_text(encoding="utf-8"))
            return Task(
                id=data.get("task_id", task_id),
                role=data.get("role", ""),
                mission_id=data.get("mission_id"),
                workspace=workspace,
            )
        role = ""
        mission_id = None
        for ev in self.bb.read_traces():
            if ev.get("task_id") == task_id and ev.get("role"):
                role = ev["role"]
            if ev.get("kind") == "brief_sent" and ev.get("task_id") == task_id:
                mission_id = (ev.get("content") or {}).get("mission_id")
        return Task(id=task_id, role=role, mission_id=mission_id, workspace=workspace)

    def sync_progress(self, task_id: str, role: str | None = None) -> dict[str, Any]:
        """Import any new progress.jsonl entries for a running task and refresh views."""
        task = self.load_task(task_id)
        role = role or task.role
        count = self.bb.sync_progress(task_id, role, task.workspace)
        return {"task_id": task_id, "imported": count}

    def submit_delivery(self, task_id: str, delivery_json: Path | None = None) -> list[dict[str, Any]]:
        """Consume a delivery written by a subagent (or by the main agent on its behalf)."""
        task = self.load_task(task_id)
        if not task.role:
            raise ValueError(f"could not determine role for task {task_id}")
        json_path = delivery_json or (task.workspace / "delivery.json")
        md_path = task.workspace / "delivery.md"
        if not json_path.is_file():
            raise FileNotFoundError(f"delivery.json not found: {json_path}")
        if not md_path.is_file():
            raise FileNotFoundError(f"delivery.md not found: {md_path}")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        payload = data.get("payload") or {}
        if isinstance(payload, dict):
            lessons = payload.get("lessons", [])
        else:
            lessons = []
        progress_path = task.workspace / "progress.jsonl"
        delivery = Delivery(
            task_id=task_id,
            role=data.get("role") or task.role,
            status=data.get("status", "submitted"),
            payload=payload,
            delivery_md=md_path.read_text(encoding="utf-8"),
            delivery_json_path=json_path,
            lessons=lessons,
            progress_path=progress_path if progress_path.is_file() else None,
        )
        return self.receive_delivery(task, delivery)

    # ------------------------------------------------------------------
    # Delivery -> timeline events
    # ------------------------------------------------------------------
    def _append_delivery_events(self, task: Task, delivery: Delivery) -> list[dict[str, Any]]:
        """Convert a delivery into timeline events according to role."""
        payload = delivery.payload
        events: list[dict[str, Any]] = []
        if task.role == "investigator":
            if isinstance(payload, dict) and "hypotheses" in payload:
                items = payload["hypotheses"]
            elif isinstance(payload, dict):
                items = [payload]
            elif isinstance(payload, list):
                items = payload
            else:
                items = [payload]
            for item in items:
                ev = self._timeline_event(
                    "hypothesis", task, delivery, {
                        "hypothesis_id": item.get("hypothesis_id", "HYP-TBD"),
                        "operation": item.get("operation", "create"),
                        "claim": item.get("claim", ""),
                        "status": item.get("status", "active"),
                        "assessment": item.get("assessment", "unassessed"),
                        "predictions": item.get("predictions", []),
                        "falsifiers": item.get("falsifiers", []),
                        "scope": item.get("scope", []),
                        "change_summary": item.get("change_summary", ""),
                        "next_best_test": item.get("next_best_test", ""),
                    }
                )
                events.append(ev)
        elif task.role == "challenger":
            events.append(self._timeline_event("challenge", task, delivery, payload))
        elif task.role == "test-designer":
            # Keep the draft as-is; the engine freeze gate will write a frozen copy.
            events.append(self._timeline_event("test_plan", task, delivery, payload))
        elif task.role == "experiment-runner":
            for run in payload.get("tool_runs", []):
                events.append(self._timeline_event("tool_run", task, delivery, run))
        elif task.role == "result-analyst":
            for obs in payload.get("observations", []):
                events.append(self._timeline_event("observation", task, delivery, obs))
            for cand in payload.get("evidence_candidates", []):
                ev = self._timeline_event("evidence_candidate", task, delivery, cand)
                events.append(ev)
        elif task.role == "evidence-reviewer":
            for review in payload.get("reviews", []):
                replies_to = self._find_evidence_candidate_event_id(review.get("evidence_id", ""))
                events.append(self._timeline_event("review", task, delivery, review, replies_to=replies_to))
        elif task.role == "mission-synthesizer":
            events.append(self._timeline_event("mission_report", task, delivery, payload))
        return events

    def _find_evidence_candidate_event_id(self, evidence_id: str) -> str | None:
        for ev in self.bb.read_timeline():
            if ev.get("type") == "evidence_candidate" and (ev.get("content") or {}).get("evidence_id") == evidence_id:
                return ev.get("id")
        return None

    def _timeline_event(
        self,
        event_type: str,
        task: Task,
        delivery: Delivery,
        content: dict[str, Any],
        replies_to: str | None = None,
    ) -> dict[str, Any]:
        summary = getattr(delivery, "summary", "") or f"The {task.role} delivered {event_type}."
        event = {
            "type": event_type,
            "role": task.role,
            "mission_id": task.mission_id,
            "task_id": task.id,
            "summary": summary,
            "content": content,
        }
        if replies_to:
            event["replies_to"] = replies_to
        event_id, _ = self.bb.append_timeline(event)
        return {"event_id": event_id, "type": event_type}

    def _validate_scientific_closure(self, data: dict[str, Any]) -> None:
        readiness = self._closure_readiness()
        if not readiness["min_outer_met"]:
            raise ValueError(
                f"scientific_closure blocked: {readiness['outer_rounds_completed']} "
                f"missions completed, but min_outer_rounds={readiness['min_outer_rounds']}"
            )
        if readiness["incomplete_missions"] or readiness["pending_tasks"]:
            reasons = []
            if readiness["incomplete_missions"]:
                reasons.append(f"incomplete missions: {readiness['incomplete_missions']}")
            if readiness["pending_tasks"]:
                reasons.append(f"pending tasks: {readiness['pending_tasks']}")
            raise ValueError(
                "scientific_closure blocked: " + "; ".join(reasons)
            )
        if (
            self.config.require_boundary_extension_resolution
            and readiness["pending_boundary_extensions"]
            and data.get("user_override") is not True
        ):
            raise ValueError(
                "scientific_closure blocked: feasible boundary_extension_candidates "
                "remain pending; resolve them as accepted_for_mission, "
                "rejected_scientific, or user_override before closure. "
                "Pending: " + "; ".join(readiness["pending_boundary_extensions"])
            )
        if self.config.closure_mode == "strict":
            final_law = data.get("final_law") or {}
            ledger = final_law.get("law_quality_ledger")
            if not isinstance(ledger, dict):
                raise ValueError(
                    "scientific_closure blocked in strict mode: final_law.law_quality_ledger "
                    "is required"
                )
            maturity = ledger.get("maturity")
            if maturity not in LAW_MATURITY:
                raise ValueError(
                    "scientific_closure blocked in strict mode: law maturity is "
                    f"{maturity!r}, expected one of {sorted(LAW_MATURITY)}"
                )
            if maturity != "law":
                raise ValueError(
                    "scientific_closure blocked in strict mode: law maturity is "
                    f"{maturity!r}, expected 'law'"
                )
            criteria = ledger.get("criteria")
            if not isinstance(criteria, dict):
                raise ValueError(
                    "scientific_closure blocked in strict mode: "
                    "final_law.law_quality_ledger.criteria must be an object"
                )
            missing = [key for key in LAW_CRITERIA if key not in criteria]
            if missing:
                raise ValueError(
                    "scientific_closure blocked in strict mode: missing law-quality "
                    f"criteria {missing}"
                )
            not_ok = {
                key: criteria[key]
                for key in LAW_CRITERIA
                if criteria[key] not in LAW_CRITERION_OK
            }
            if not_ok:
                raise ValueError(
                    "scientific_closure blocked in strict mode: law-quality criteria "
                    f"must be pass/not_applicable, got {not_ok}"
                )
            if readiness["pending_research_frontier"]:
                raise ValueError(
                    "scientific_closure blocked in strict mode: pending high/medium "
                    "research frontier: " + "; ".join(readiness["pending_research_frontier"])
                )
            for field in ("statement", "boundaries", "recommendation"):
                if not final_law.get(field):
                    raise ValueError(
                        "scientific_closure blocked in strict mode: final_law."
                        f"{field} is required"
                    )
            oqs = final_law.get("open_questions") or []
            if not isinstance(oqs, list):
                raise ValueError(
                    "scientific_closure blocked in strict mode: final_law.open_questions "
                    "must be a list with status dispositions"
                )
            for q in oqs:
                if not isinstance(q, dict) or q.get("status") not in {
                    "resolved", "out_of_scope", "deferred",
                }:
                    raise ValueError(
                        "scientific_closure blocked in strict mode: each open question "
                        "must have status resolved/out_of_scope/deferred"
                    )
            dr = final_law.get("divergence_review")
            if not isinstance(dr, dict) or dr.get("decision") not in {
                "open_mission", "not_testable", "user_override",
            }:
                raise ValueError(
                    "scientific_closure blocked in strict mode: final_law.divergence_review "
                    "must have decision open_mission/not_testable/user_override"
                )
            if dr.get("decision") == "open_mission":
                raise ValueError(
                    "scientific_closure blocked: divergence_review.decision is "
                    "open_mission; open a new Mission instead"
                )

    @staticmethod
    def _mark_consumed(round_dir: Path, kind: str, payload: dict[str, Any]) -> None:
        (round_dir / f"{kind}.consumed.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
