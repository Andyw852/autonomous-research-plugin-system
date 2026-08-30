import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine.config import load_config
from scripts.engine.models import Brief, Delivery, Task
from scripts.engine.protocol import ProtocolEngine
from scripts.engine.subagents import FakeSubagentBackend
from scripts.engine.validation import validate_delivery

ROOT = Path(__file__).resolve().parents[2]


def _await_and_submit(engine, mission_id, role, payload=None):
    """Advance one step without a backend, then submit a (possibly overridden) fake delivery."""
    import json

    result = None
    for _ in range(20):
        candidate = engine.advance(mission_id, {})
        if candidate["status"] == "gate":
            continue
        result = candidate
        break
    assert result is not None and result["status"] == "awaiting_subagent", result
    task_id = result["task_id"]
    workspace = Path(result["workspace"])
    brief = Brief(
        role=role,
        task_id=task_id,
        mission_id=mission_id,
        content=result.get("brief") or {},
        workspace=workspace,
    )
    FakeSubagentBackend().dispatch(task_id, role, brief)
    if payload is not None:
        delivery_json_path = workspace / "delivery.json"
        data = json.loads(delivery_json_path.read_text(encoding="utf-8"))
        data["payload"] = payload
        delivery_json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    events = engine.submit_delivery(task_id)
    return events, workspace, task_id



class ConfigTest(unittest.TestCase):
    def test_load_config(self):
        config = load_config(ROOT / "config" / "plugin.config.yaml")
        self.assertEqual(config.name, "autonomous-research-engine")
        self.assertTrue((config.agents_dir / "investigator.md").is_file())


class CampaignIsolationTest(unittest.TestCase):
    def test_start_creates_campaign_subfolder(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            engine = ProtocolEngine(config)
            engine.start_campaign("Isolation test")
            self.assertTrue(engine.bb.run_root.name.startswith("CAM-"))
            self.assertTrue((engine.bb.run_root / "timeline.jsonl").is_file())
            self.assertFalse((config.run_root / "timeline.jsonl").exists())

    def test_start_always_creates_new_campaign_subfolder(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.run_root.mkdir(parents=True, exist_ok=True)
            # Simulate a polluted run root: an old log at the root must not cause reuse.
            (config.run_root / "timeline.jsonl").write_text("{}\n", encoding="utf-8")
            engine = ProtocolEngine(config)
            engine.start_campaign("New campaign")
            self.assertTrue(engine.bb.run_root.name.startswith("CAM-"))
            self.assertEqual(engine.bb.run_root.parent, config.run_root)
            self.assertTrue((engine.bb.run_root / "timeline.jsonl").is_file())

    def test_direction_review_consumed(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            engine = ProtocolEngine(config)
            engine.start_campaign("Direction review test")
            round_dir = engine.bb.run_root / "blackboard" / "directives" / "round-1"
            round_dir.mkdir(parents=True, exist_ok=True)
            (round_dir / "direction_review.json").write_text(
                json.dumps({
                    "target": "proposal",
                    "verdict": "revise",
                    "summary": "The proposal needs a stronger mechanism contrast.",
                    "blocking_issues": [],
                    "required_changes": ["Name the decisive control."],
                    "law_quality_assessment": {
                        "candidate_is_scientific_law": True,
                        "current_maturity": "rule_candidate",
                        "unresolved_gaps": ["controlled_discrimination"],
                    },
                    "frontier_alignment": {
                        "selected_frontier": "mechanism contrast",
                        "is_highest_priority_pending": True,
                        "reason": "It addresses the top pending gap.",
                    },
                    "capability_gap": {"present": False, "missing_capability": "none"},
                }),
                encoding="utf-8",
            )
            consumed = engine.consume_directives()
            self.assertEqual(len(consumed), 1)
            self.assertEqual(consumed[0]["kind"], "direction_review")
            timeline = engine.bb.read_timeline()
            self.assertEqual(timeline[-1]["type"], "direction_review")
            self.assertEqual(timeline[-1]["role"], "direction-reviewer")
            self.assertEqual(timeline[-1]["content"]["verdict"], "revise")


class ValidationTest(unittest.TestCase):
    def test_delivery_role_mismatch(self):
        task = Task(id="TSK-1", role="investigator", workspace=Path("/tmp"))
        delivery = Delivery(
            task_id="TSK-1", role="challenger", status="submitted", payload={},
            delivery_md="x" * 100, delivery_json_path=Path("/tmp/nope.json"),
        )
        errors = validate_delivery(task, delivery)
        self.assertTrue(any("task role" in e for e in errors))

    def test_fake_delivery_valid(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            task = Task(id="TSK-2", role="investigator", workspace=workspace)
            brief = Brief(
                role="investigator", task_id="TSK-2", mission_id=None,
                content={}, workspace=workspace,
            )
            delivery = FakeSubagentBackend().dispatch("TSK-2", "investigator", brief)
            errors = validate_delivery(task, delivery)
            self.assertEqual(errors, [])


class Phase4EdgeTest(unittest.TestCase):
    def _new_engine(self, td):
        config = load_config(ROOT / "config" / "plugin.config.yaml")
        config.run_root = Path(td) / "runs"
        # No backend; we drive subagent creation manually like the main agent.
        return ProtocolEngine(config)

    def _start_mission(self, engine):
        engine.start_campaign("Phase4 edge test")
        mission_id = engine.bb.events.new_id("MIS")
        engine.admit_mission(mission_id, {"research_question": "Phase4"})
        return mission_id

    def test_rejected_review_flow(self):
        with tempfile.TemporaryDirectory() as td:
            engine = self._new_engine(td)
            mission_id = self._start_mission(engine)
            # Drive through all pre-review roles.
            _await_and_submit(engine, mission_id, "investigator")
            _await_and_submit(engine, mission_id, "challenger")
            _await_and_submit(engine, mission_id, "test-designer")
            _await_and_submit(engine, mission_id, "experiment-runner")
            _await_and_submit(engine, mission_id, "result-analyst")
            # Submit a rejected review.
            payload = {
                "independence_declaration": "independent",
                "reviews": [
                    {
                        "evidence_id": "EVD-TBD",
                        "verdict": "needs_more_work",
                        "reasons": "The fake candidate needs more controls.",
                        "permitted_scope": None,
                        "required_work": "Add controls.",
                    }
                ],
            }
            events, _, _ = _await_and_submit(engine, mission_id, "evidence-reviewer", payload)
            self.assertEqual(events[0]["type"], "review")
            self.assertEqual(engine.validate(), [])

    def test_frozen_gate_blocks_runner_without_plan(self):
        with tempfile.TemporaryDirectory() as td:
            engine = self._new_engine(td)
            mission_id = self._start_mission(engine)
            _await_and_submit(engine, mission_id, "investigator")
            _await_and_submit(engine, mission_id, "challenger")
            # Try to run the experiment before any test_plan exists.
            with self.assertRaises(ValueError):
                _await_and_submit(engine, mission_id, "experiment-runner")

    def test_experience_filter(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            engine = ProtocolEngine(config)
            engine.start_campaign("Experience test")
            engine.bb.experience_add(
                category="tool",
                summary="A useful tool tip",
                detail="Details",
                source_role="experiment-runner",
            )
            engine.bb.experience_add(
                category="workflow",
                summary="A useful workflow tip",
                detail="Details",
                source_role="investigator",
            )
            from scripts.engine.experience import relevant_entries
            self.assertEqual(len(relevant_entries(engine.bb, role="investigator")), 1)
            self.assertEqual(
                relevant_entries(engine.bb, role="investigator")[0]["summary"],
                "A useful workflow tip",
            )

    def test_hypothesis_count_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.min_hypotheses = 2
            config.max_hypotheses = 3
            engine = ProtocolEngine(config)
            engine.start_campaign("Hyp bounds")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Bounds"})
            result = engine.advance(mission_id, {})
            task_id = result["task_id"]
            workspace = Path(result["workspace"])
            payload = {
                "hypotheses": [
                    {"hypothesis_id": "HYP-1", "operation": "create", "claim": "one"},
                    {"hypothesis_id": "HYP-2", "operation": "create", "claim": "two"},
                    {"hypothesis_id": "HYP-3", "operation": "create", "claim": "three"},
                    {"hypothesis_id": "HYP-4", "operation": "create", "claim": "four"},
                ]
            }
            import json
            (workspace / "delivery.json").write_text(
                json.dumps({"role": "investigator", "task_id": task_id, "status": "submitted", "payload": payload}, indent=2),
                encoding="utf-8",
            )
            (workspace / "delivery.md").write_text(
                "1. What I reviewed: x.\n2. My main findings: y.\n3. Concrete changes: none.\n4. Expected impact: z.\n5. Residual risks: none.\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                engine.submit_delivery(task_id)

    def test_scientific_closure_gate(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            config.max_inner_rounds = 1
            config.min_outer_rounds = 2
            config.closure_mode = "strict"
            engine = ProtocolEngine(config)
            engine.start_campaign("Closure gate")
            mid1 = engine.bb.events.new_id("MIS")
            engine.admit_mission(mid1, {"research_question": "M1"})
            engine.run_inner_loop_full(mid1, {})
            # One completed mission is below min_outer_rounds.
            with self.assertRaises(ValueError):
                engine._validate_scientific_closure({"final_law": {"open_questions": []}})
            # Complete second mission.
            mid2 = engine.bb.events.new_id("MIS")
            engine.admit_mission(mid2, {"research_question": "M2"})
            engine.run_inner_loop_full(mid2, {})
            # Strict mode requires law-level maturity before open-question checks.
            with self.assertRaises(ValueError):
                engine._validate_scientific_closure({"final_law": {"open_questions": []}})
            ledger = {
                "law_candidate": "fake law candidate",
                "maturity": "law",
                "criteria": {
                    "mechanism": "pass",
                    "controlled_discrimination": "pass",
                    "generality": "pass",
                    "boundary_map": "pass",
                    "decision_utility": "pass",
                    "reproducibility": "not_applicable",
                },
                "gaps": [],
            }
            # A criterion that remains partial blocks closure.
            partial_ledger = dict(ledger)
            partial_ledger["criteria"] = dict(ledger["criteria"])
            partial_ledger["criteria"]["generality"] = "partial"
            with self.assertRaises(ValueError):
                engine._validate_scientific_closure({
                    "final_law": {
                        "law_quality_ledger": partial_ledger,
                        "open_questions": [],
                    }
                })
            # Strict mode requires every open question to carry a status.
            with self.assertRaises(ValueError):
                engine._validate_scientific_closure({
                    "final_law": {
                        "law_quality_ledger": ledger,
                        "open_questions": ["unresolved?"],
                    }
                })
            # Valid structured open questions pass.
            engine._validate_scientific_closure({
                "final_law": {
                    "statement": "A fake mechanism-level law.",
                    "boundaries": "Fake boundary.",
                    "recommendation": "Use the fake shortlist.",
                    "law_quality_ledger": ledger,
                    "open_questions": [
                        {"question": "q1", "status": "out_of_scope", "reason": "not in scope"}
                    ],
                    "divergence_review": {
                        "alternative_perspective": "different perspective",
                        "testable": False,
                        "new_scientific_value": "low",
                        "decision": "not_testable"
                    }
                }
            })

        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            engine = ProtocolEngine(config)
            engine.start_campaign("Status incomplete")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Incomplete"})
            engine.advance(mission_id, {})
            status = engine.round_status()
            self.assertIn(mission_id, status["incomplete_missions"])
            self.assertEqual(len(status["pending_tasks"]), 1)

        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            engine = ProtocolEngine(config)
            engine.start_campaign("Progress test")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Progress"})
            result = engine.advance(mission_id, {})
            self.assertEqual(result["status"], "awaiting_subagent")
            task_id = result["task_id"]
            workspace = Path(result["workspace"])
            progress = workspace / "progress.jsonl"
            progress.write_text(
                '{"kind": "attempt_start", "summary": "started"}\n'
                '{"kind": "tool_run", "summary": "tool done", "content": {"tool_name": "fake"}}\n',
                encoding="utf-8",
            )
            first = engine.sync_progress(task_id)
            self.assertEqual(first["imported"], 2)
            second = engine.sync_progress(task_id)
            self.assertEqual(second["imported"], 0)
            with progress.open("a", encoding="utf-8") as handle:
                handle.write('{"kind": "status_change", "summary": "progressing"}\n')
            third = engine.sync_progress(task_id)
            self.assertEqual(third["imported"], 1)
            traces = engine.bb.read_traces()
            progress_kinds = {"attempt_start", "attempt_end", "tool_run", "status_change"}
            task_traces = [
                e for e in traces
                if e.get("task_id") == task_id and e.get("kind") in progress_kinds
            ]
            self.assertEqual(len(task_traces), 3)

    def test_experience_imported_in_full_loop(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            config.max_inner_rounds = 1
            engine = ProtocolEngine(config)
            engine.start_campaign("Experience full loop")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Exp"})
            engine.run_inner_loop_full(mission_id, {})
            entries = engine.bb.experience_list()
            self.assertGreaterEqual(len(entries), 7)

    def test_artifacts_preserved_in_full_loop(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            config.max_inner_rounds = 1
            engine = ProtocolEngine(config)
            engine.start_campaign("Artifact test")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Artifacts"})
            engine.run_inner_loop_full(mission_id, {})
            artifact_files = list((engine.bb.run_root / "artifacts").rglob("raw_scores.json"))
            self.assertEqual(len(artifact_files), 1)
            self.assertEqual(engine.validate(), [])

    def test_round_status_after_full_loop(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            engine = ProtocolEngine(config)
            engine.start_campaign("Status test")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Status"})
            engine.run_inner_loop_full(mission_id, {})
            status = engine.round_status()
            self.assertEqual(status["active_mission_count"], 1)
            self.assertEqual(status["hypothesis_count"], 1)
            self.assertIsNotNone(status["latest_mission_report"])


class ProtocolSmokeTest(unittest.TestCase):
    def test_smoke_inner_loop(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            config.max_inner_rounds = 1
            engine = ProtocolEngine(config)
            engine.start_campaign("Smoke test objective")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Smoke"})
            steps = engine.run_inner_loop_full(mission_id, {"research_question": "Smoke"})
            self.assertEqual(steps[-1]["status"], "complete")
            self.assertEqual(engine.validate(), [])
            state = engine.build_snapshot()
            self.assertEqual(len(state.mission_reports), 1)
            self.assertEqual(len(state.tasks), 7)

    def test_submit_delivery_flow(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            # No backend: engine emits awaiting_subagent for the main agent.
            engine = ProtocolEngine(config)
            engine.start_campaign("Submit delivery test")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Submit"})
            result = engine.advance(mission_id, {"research_question": "Submit"})
            self.assertEqual(result["status"], "awaiting_subagent")
            self.assertEqual(result["role"], "investigator")
            task_id = result["task_id"]
            workspace = Path(result["workspace"])
            payload = {
                "hypothesis_id": "HYP-001",
                "operation": "create",
                "claim": "A test claim.",
                "status": "active",
                "assessment": "unassessed",
                "predictions": [],
                "falsifiers": [],
                "scope": [],
                "change_summary": "test",
            }
            delivery_json = {
                "role": "investigator",
                "task_id": task_id,
                "status": "submitted",
                "payload": payload,
            }
            (workspace / "delivery.json").write_text(
                __import__("json").dumps(delivery_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (workspace / "delivery.md").write_text(
                "1. What I reviewed: test.\n2. My main findings: test.\n"
                "3. Concrete changes: none.\n4. Expected impact: test.\n5. Residual risks: none.\n",
                encoding="utf-8",
            )
            events = engine.submit_delivery(task_id)
            self.assertEqual(events[0]["type"], "hypothesis")
            self.assertEqual(engine.validate(), [])

    def test_multi_round_inner_loop(self):
        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            config.max_inner_rounds = 2
            engine = ProtocolEngine(config)
            engine.start_campaign("Multi-round test")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Multi-round"})
            steps = engine.run_inner_loop_full(mission_id, {"research_question": "Multi-round"})
            self.assertEqual(steps[-1]["status"], "complete")
            self.assertEqual(engine.validate(), [])
            state = engine.build_snapshot()
            self.assertEqual(len(state.mission_reports), 1)
            # Two rounds of 6 subagent roles each + mission-synthesizer = 13 tasks.
            self.assertEqual(len(state.tasks), 13)

        with tempfile.TemporaryDirectory() as td:
            config = load_config(ROOT / "config" / "plugin.config.yaml")
            config.run_root = Path(td) / "runs"
            config.subagent_backend = "fake"
            config.max_inner_rounds = 1
            engine = ProtocolEngine(config)
            engine.start_campaign("Advance test objective")
            mission_id = engine.bb.events.new_id("MIS")
            engine.admit_mission(mission_id, {"research_question": "Advance"})
            steps = engine.run_inner_loop_full(mission_id, {"research_question": "Advance"})
            self.assertEqual(steps[-1]["status"], "complete")
            self.assertEqual(engine.validate(), [])
            state = engine.build_snapshot()
            self.assertEqual(len(state.mission_reports), 1)
            self.assertEqual(len(state.tasks), 7)


if __name__ == "__main__":
    unittest.main()
