#!/usr/bin/env python3
"""Main-agent style smoke test.

This script drives the engine exactly like a main agent would in production:
1. engine.next() returns awaiting_subagent
2. the "main agent" creates a subagent (here: FakeSubagentBackend writes delivery files)
3. engine.submit_delivery() consumes it

Run from the plugin root:
    python3 scripts/smoke_main_agent.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.engine.config import load_config
from scripts.engine.models import Brief
from scripts.engine.protocol import ProtocolEngine
from scripts.engine.subagents import FakeSubagentBackend


def main() -> int:
    run_root = Path(tempfile.mkdtemp(prefix="ars-main-agent-smoke-"))
    config = load_config(Path(__file__).resolve().parents[1] / "config" / "plugin.config.yaml")
    config.run_root = run_root

    engine = ProtocolEngine(config)  # no backend: production-like
    engine.start_campaign("Main-agent style smoke test")

    mission_id = engine.bb.events.new_id("MIS")
    engine.admit_mission(mission_id, {"research_question": "Main-agent style smoke"})

    fake = FakeSubagentBackend()
    steps = 0
    while True:
        result = engine.advance(mission_id, {"research_question": "Main-agent style smoke"})
        print(result["status"], result.get("phase", ""), result.get("role", ""))
        if result["status"] == "complete":
            break
        if result["status"] == "gate":
            # Deterministic engine gate; no subagent needed.
            continue
        if result["status"] != "awaiting_subagent":
            raise RuntimeError(f"unexpected step result: {result}")
        task_id = result["task_id"]
        workspace = Path(result["workspace"])
        role = result["role"]
        brief = Brief(
            role=role,
            task_id=task_id,
            mission_id=mission_id,
            content=result.get("brief") or {},
            workspace=workspace,
        )
        fake.dispatch(task_id, role, brief)
        engine.submit_delivery(task_id)
        steps += 1
        if steps > 30:
            raise RuntimeError("smoke loop did not terminate")

    errors = engine.validate()
    if errors:
        print("VALIDATION ERRORS:")
        for err in errors:
            print(" -", err)
        return 1

    status = engine.round_status()
    print("\nRun root:", engine.bb.run_root)
    print("Steps:", steps)
    print("Status:", json.dumps(status, ensure_ascii=False, default=str, indent=2))
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
