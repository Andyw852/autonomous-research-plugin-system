"""Command line interface for the autonomous-research plugin."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .protocol import ProtocolEngine
from .subagents import FakeSubagentBackend


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research", description="Autonomous research plugin")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--run-root", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="initialize a campaign")
    p_init.add_argument("--objective", required=True)

    p_propose = sub.add_parser("propose", help="install a Director proposal directive")
    p_propose.add_argument("--round", required=True, type=int)
    p_propose.add_argument("--proposal", required=True, type=Path)
    p_consume = sub.add_parser("consume-directives", help="consume pending Director directives")
    p_admit = sub.add_parser("admit-mission", help="admit a Mission")
    p_admit.add_argument("--mission", required=True)
    p_admit.add_argument("--proposal", type=Path, default=None)
    sub.add_parser("snapshot", help="print the reconstructed research state")
    sub.add_parser("status", help="print a concise outer-loop status report")
    sub.add_parser("validate", help="validate the run logs")
    sub.add_parser("smoke", help="run a fake full inner loop for testing")
    p_smoke = sub.add_parser("smoke-mission", help="run a fake inner loop for a mission")
    p_smoke.add_argument("--mission", required=True)
    p_next = sub.add_parser("next", help="advance one deterministic protocol step")
    p_next.add_argument("--mission", required=True)
    p_submit = sub.add_parser("submit-delivery", help="submit a subagent delivery")
    p_submit.add_argument("--task", required=True)
    p_submit.add_argument("--delivery", type=Path, default=None)
    p_sync = sub.add_parser("sync-progress", help="import new progress entries from a running task")
    p_sync.add_argument("--task", required=True)
    p_sync.add_argument("--role", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    if args.run_root:
        config.run_root = args.run_root.resolve()
    engine = ProtocolEngine(config)

    campaign_commands = {
        "propose", "consume-directives", "admit-mission", "snapshot", "status",
        "validate", "smoke-mission", "next", "submit-delivery", "sync-progress",
    }
    if args.command in campaign_commands:
        if not args.run_root:
            raise SystemExit(
                "This command requires --run-root <CAM dir>; use the campaign path printed by init."
            )
        if not (engine.bb.run_root / "timeline.jsonl").is_file():
            raise SystemExit(
                f"--run-root must point to an initialized campaign directory: {engine.bb.run_root}"
            )

    if args.command == "init":
        result = engine.start_campaign(args.objective)
        print(f"Initialized campaign at {engine.bb.run_root}")
        print(result)
    elif args.command == "propose":
        import json
        data = json.loads(args.proposal.read_text(encoding="utf-8"))
        target = engine.bb.run_root / "blackboard" / "directives" / f"round-{args.round}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "proposal.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        md_src = args.proposal.with_suffix(".md")
        if md_src.is_file():
            (target / "proposal.md").write_text(md_src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Proposal installed at {target / 'proposal.json'}")
    elif args.command == "consume-directives":
        consumed = engine.consume_directives()
        print(consumed)
    elif args.command == "admit-mission":
        proposal = None
        if args.proposal:
            import json
            proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
        result = engine.admit_mission(args.mission, proposal)
        print(result)
    elif args.command == "snapshot":
        state = engine.build_snapshot()
        print(f"campaign: {state.campaign}")
        print(f"missions: {len(state.missions)}")
        print(f"hypotheses: {len(state.hypotheses)}")
        print(f"evidence: {len(state.evidence)}")
        print(f"tasks: {len(state.tasks)}")
    elif args.command == "status":
        print(engine.round_status())
    elif args.command == "validate":
        errors = engine.validate()
        if errors:
            print("VALIDATION ERRORS:")
            for error in errors:
                print(" -", error)
            return 1
        print("OK")
    elif args.command == "smoke":
        engine.backend = FakeSubagentBackend()
        engine.start_campaign("fake smoke campaign")
        mission_id = engine.bb.events.new_id("MIS")
        engine.admit_mission(mission_id, {"research_question": "fake smoke mission"})
        steps = engine.run_inner_loop_full(mission_id, {"research_question": "fake smoke mission"})
        print(f"Ran {len(steps)} steps for {mission_id} in {engine.bb.run_root}")
    elif args.command == "smoke-mission":
        engine.backend = FakeSubagentBackend()
        steps = engine.run_inner_loop_full(args.mission, {})
        print(f"Ran {len(steps)} steps")
    elif args.command == "next":
        # The main agent is responsible for creating the subagent; the engine only
        # creates the task and returns the brief.
        result = engine.advance(args.mission, {})
        print(result)
    elif args.command == "submit-delivery":
        events = engine.submit_delivery(args.task, args.delivery)
        print({"status": "delivered", "events": events})
    elif args.command == "sync-progress":
        result = engine.sync_progress(args.task, args.role)
        print(result)
    else:
        build_parser().print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
