#!/usr/bin/env python3
"""Event and trace log layer: append, validate, replay, state modeling, checkpoint, restore.

This module is the single machine-authoritative layer of the research blackboard:
- timeline.jsonl records research events (hypothesis, challenge, test plan, tool run,
  observation, evidence, review, decision, mission report).
- traces.jsonl records the operational trajectory of every agent task.

Both logs are append-only JSONL. A checkpoint records the sha256 and line counts of
both files; restore verifies integrity and replays the logs. This module does not
generate HTML (render.py is responsible for all derived views).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Basic utilities
# ---------------------------------------------------------------------------

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid() -> str:
    """Generate a 26-character Crockford base32 ULID (48-bit ms timestamp + 80-bit random)."""
    ts = int(time.time() * 1000)
    ts_part = []
    for _ in range(10):
        ts_part.append(_CROCKFORD[ts & 31])
        ts >>= 5
    rand = int.from_bytes(os.urandom(10), "big")
    rand_part = []
    for _ in range(16):
        rand_part.append(_CROCKFORD[rand & 31])
        rand >>= 5
    return "".join(reversed(ts_part)) + "".join(rand_part)


def new_id(prefix: str) -> str:
    return f"{prefix}-{ulid()}"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".%03dZ" % (
        time.time() % 1 * 1000
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Log paths
# ---------------------------------------------------------------------------

def _log_path(run_root: Path, kind: str) -> Path:
    return run_root / f"{kind}.jsonl"  # kind in {"timeline", "traces"}


def append_event(run_root: Path, kind: str, event: dict) -> tuple[str, int]:
    """Append one event line to the named log. Return (event id, 1-based line number)."""
    if kind not in {"timeline", "traces"}:
        raise ValueError(f"unknown log kind: {kind}")
    if event.get("schema") is None:
        event["schema"] = "research-event/1" if kind == "timeline" else "trace-event/1"
    if event.get("id") is None:
        event["id"] = new_id("EVT" if kind == "timeline" else "TRC")
    if event.get("created_at") is None:
        event["created_at"] = now_iso()
    ev = {k: v for k, v in event.items() if v is not None}
    path = _log_path(run_root, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(ev, ensure_ascii=False) + "\n")
    with path.open("r", encoding="utf-8") as handle:
        line_count = sum(1 for _ in handle)
    return ev["id"], line_count


def read_log(run_root: Path, kind: str) -> list[dict]:
    """Read the whole log as a list of dicts. Return [] when the file is missing or empty."""
    path = _log_path(run_root, kind)
    if not path.is_file():
        return []
    events: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_no} JSON parse failed: {exc}") from exc
    return events


def log_metrics(run_root: Path, kind: str) -> dict:
    """Return the log sha256 and line count (used by checkpoints and restore)."""
    path = _log_path(run_root, kind)
    if not path.is_file():
        return {"sha256": None, "lines": 0}
    return {"sha256": sha256_file(path), "lines": path.read_text(encoding="utf-8").count("\n")}


# ---------------------------------------------------------------------------
# Event validation (lightweight)
# ---------------------------------------------------------------------------

ROLES = {
    "director", "orchestrator", "investigator", "challenger", "test-designer",
    "experiment-runner", "result-analyst", "evidence-reviewer", "mission-synthesizer",
    "direction-reviewer",
}

TIMELINE_TYPES = {
    "campaign_init", "mission_proposal", "mission_admit", "hypothesis",
    "challenge", "test_plan", "tool_run", "observation", "evidence_candidate",
    "review", "direction_review", "decision", "mission_report", "note", "checkpoint",
}

HYPOTHESIS_OPERATIONS = {"create", "refine", "split", "merge", "supersede", "retire", "assessment-update"}

ASSESSMENTS = {"unassessed", "supported", "weakened", "mixed", "refuted"}

HYPOTHESIS_LIFECYCLE = {"proposed", "active", "under_test", "dormant", "superseded", "retired"}

REVIEW_VERDICTS = {"accepted", "rejected", "needs_more_work"}

DIRECTION_REVIEW_TARGETS = {"proposal", "next_direction", "terminal_decision"}

DIRECTION_REVIEW_VERDICTS = {"approve", "revise", "reject"}

MISSION_VERDICTS = {"converged", "inconclusive", "not_testable", "blocked", "mixed"}

TRACE_KINDS = {
    "task_start", "brief_sent", "attempt_start", "attempt_end", "tool_run",
    "delivery_received", "status_change", "task_end", "checkpoint",
}

# Required top-level fields per event type (beyond the common fields).
_TIMELINE_REQUIRED = {
    "campaign_init": {"summary", "content"},
    "mission_proposal": {"summary", "content"},
    "mission_admit": {"summary", "mission_id", "content"},
    "hypothesis": {"summary", "mission_id", "content"},
    "challenge": {"summary", "mission_id", "content"},
    "test_plan": {"summary", "mission_id", "content"},
    "tool_run": {"summary", "mission_id", "task_id", "content"},
    "observation": {"summary", "mission_id", "content"},
    "evidence_candidate": {"summary", "mission_id", "content"},
    "review": {"summary", "mission_id", "content"},
    "direction_review": {"summary", "content"},
    "decision": {"summary", "content"},  # mission_id optional: campaign-level decisions carry none
    "mission_report": {"summary", "mission_id", "content"},
    "note": {"summary"},
    "checkpoint": {"summary"},
}

_TRACE_REQUIRED = {
    "task_start": {"task_id", "role", "content"},
    "brief_sent": {"task_id", "role", "content"},
    "attempt_start": {"task_id", "content"},
    "attempt_end": {"task_id", "content"},
    "tool_run": {"task_id", "content"},
    "delivery_received": {"task_id", "content"},
    "status_change": {"task_id", "content"},
    "task_end": {"task_id", "content"},
    "checkpoint": {},
}

_COMMON_TIMELINE = {"schema", "id", "type", "role", "summary", "created_at"}
_COMMON_TRACE = {"schema", "id", "task_id", "role", "kind", "summary", "created_at"}


def _type_check(event: dict, common: set[str], required: dict, name: str) -> list[str]:
    errors: list[str] = []
    for field in required.get(event.get("type", ""), set()) | common:
        if field not in event:
            errors.append(f"{name} {event.get('id', '?')}: missing top-level field {field}")
    return errors


def _content_check(event: dict, name: str) -> list[str]:
    """Lightweight per-type checks on the content object."""
    errors: list[str] = []
    etype, content = event.get("type"), event.get("content")
    if etype not in TIMELINE_TYPES:
        return errors  # unknown-type handling lives in _type_check
    if not isinstance(content, dict):
        if etype not in {"note", "checkpoint"}:
            errors.append(f"{name} {event.get('id', '?')}: content must be an object")
        return errors
    if etype == "hypothesis":
        hid = content.get("hypothesis_id")
        if not hid or not str(hid).startswith("HYP-"):
            errors.append(f"{name} {event.get('id', '?')}: hypothesis event missing content.hypothesis_id")
        if content.get("operation") not in HYPOTHESIS_OPERATIONS:
            errors.append(f"{name} {event.get('id', '?')}: invalid hypothesis operation")
        if not content.get("claim") and content.get("operation") not in {
            "assessment-update", "retire",
        }:
            errors.append(f"{name} {event.get('id', '?')}: hypothesis event missing content.claim")
        if content.get("assessment") and content["assessment"] not in ASSESSMENTS:
            errors.append(f"{name} {event.get('id', '?')}: invalid assessment")
        if content.get("lifecycle") and content["lifecycle"] not in HYPOTHESIS_LIFECYCLE:
            errors.append(f"{name} {event.get('id', '?')}: invalid lifecycle")
    elif etype == "challenge":
        if not content.get("target_hypothesis_id") and not content.get("target_ids"):
            errors.append(f"{name} {event.get('id', '?')}: challenge event missing target hypothesis")
    elif etype == "test_plan":
        if content.get("frozen") is None and content.get("status") not in {"frozen", "draft", "rejected"}:
            errors.append(f"{name} {event.get('id', '?')}: test_plan event missing frozen/status")
    elif etype == "review":
        if content.get("verdict") not in REVIEW_VERDICTS:
            errors.append(f"{name} {event.get('id', '?')}: invalid review verdict")
        if not content.get("evidence_id"):
            errors.append(f"{name} {event.get('id', '?')}: review event missing evidence_id")
    elif etype == "direction_review":
        if content.get("target") not in DIRECTION_REVIEW_TARGETS:
            errors.append(f"{name} {event.get('id', '?')}: invalid direction_review target")
        if content.get("verdict") not in DIRECTION_REVIEW_VERDICTS:
            errors.append(f"{name} {event.get('id', '?')}: invalid direction_review verdict")
    elif etype == "evidence_candidate":
        if not content.get("evidence_id") and not content.get("hypothesis_id"):
            errors.append(f"{name} {event.get('id', '?')}: evidence_candidate event missing evidence/hypothesis reference")
    elif etype == "tool_run":
        if content.get("status") not in {None, "succeeded", "failed", "timed_out", "cancelled"}:
            errors.append(f"{name} {event.get('id', '?')}: invalid tool_run status")
    elif etype == "mission_report":
        if content.get("mission_verdict") not in MISSION_VERDICTS:
            errors.append(f"{name} {event.get('id', '?')}: invalid mission_verdict")
        for update in content.get("hypothesis_updates") or []:
            if not isinstance(update, dict) or not update.get("hypothesis_id"):
                errors.append(f"{name} {event.get('id', '?')}: hypothesis_updates entries require hypothesis_id")
        for item in content.get("evidence_summary") or []:
            if not isinstance(item, dict) or not item.get("evidence_id"):
                errors.append(f"{name} {event.get('id', '?')}: evidence_summary entries require evidence_id")
    return errors


def validate_timeline_event(event: dict, run_root: Path, name: str = "timeline") -> list[str]:
    errors = _type_check(event, _COMMON_TIMELINE, _TIMELINE_REQUIRED, name)
    errors += _content_check(event, name)
    if event.get("type") and event["type"] not in TIMELINE_TYPES:
        errors.append(f"{name} {event.get('id', '?')}: unknown event type {event['type']}")
    if event.get("role") and event["role"] not in ROLES:
        errors.append(f"{name} {event.get('id', '?')}: unknown role {event['role']}")
    if event.get("replies_to") and not event["replies_to"].startswith("EVT-"):
        errors.append(f"{name} {event.get('id', '?')}: replies_to must be an EVT- event id")
    errors += _validate_refs(event, run_root, name)
    return errors


def validate_trace_event(event: dict, run_root: Path, name: str = "traces") -> list[str]:
    errors = _type_check(event, _COMMON_TRACE, _TRACE_REQUIRED, name)
    if event.get("kind") and event["kind"] not in TRACE_KINDS:
        errors.append(f"{name} {event.get('id', '?')}: unknown trace kind {event['kind']}")
    if event.get("role") and event["role"] not in ROLES:
        errors.append(f"{name} {event.get('id', '?')}: unknown role {event['role']}")
    errors += _validate_refs(event, run_root, name)
    return errors


def _validate_refs(event: dict, run_root: Path, name: str) -> list[str]:
    """Check that referenced files exist inside the run root and match their sha256."""
    errors: list[str] = []
    for key in ("refs", "artifacts"):
        for ref in event.get(key) or []:
            path_text = ref.get("path") if isinstance(ref, dict) else None
            if not path_text:
                continue
            if Path(path_text).is_absolute():
                errors.append(f"{name} {event.get('id', '?')}: absolute paths are forbidden: {path_text}")
                continue
            target = (run_root / path_text).resolve()
            try:
                target.relative_to(run_root.resolve())
            except ValueError:
                errors.append(f"{name} {event.get('id', '?')}: reference escapes the run root: {path_text}")
                continue
            if not target.is_file():
                errors.append(f"{name} {event.get('id', '?')}: referenced file does not exist: {path_text}")
                continue
            expected = ref.get("sha256")
            if expected:
                actual = sha256_file(target)
                if actual != expected:
                    errors.append(f"{name} {event.get('id', '?')}: sha256 mismatch: {path_text}")
    return errors


def _policy_checks(events: list[dict], run_root: Path) -> list[str]:
    """Cross-event policy checks: independent review, authorship separation."""
    errors: list[str] = []
    by_id = {ev["id"]: ev for ev in events}
    hyp_author = {}
    for ev in events:
        if ev.get("type") == "hypothesis":
            hid = (ev.get("content") or {}).get("hypothesis_id")
            if hid:
                hyp_author.setdefault(hid, (ev.get("role"), ev.get("id")))
    for ev in events:
        if ev.get("type") != "review":
            continue
        content = ev.get("content") or {}
        verdict = content.get("verdict")
        target = by_id.get(ev.get("replies_to") or "") if ev.get("replies_to") else None
        if verdict == "accepted":
            if target is None or target.get("type") != "evidence_candidate":
                errors.append(f"timeline {ev['id']}: an accepted review must reply to an evidence_candidate event")
        # Independence: a hypothesis author may not review evidence for their own claim.
        if target and target.get("type") == "evidence_candidate":
            thid = (target.get("content") or {}).get("hypothesis_id")
            author_role = hyp_author.get(thid, (None, None))[0]
            if author_role and author_role == ev.get("role"):
                errors.append(f"timeline {ev['id']}: hypothesis author {author_role} may not review their own evidence")
    return errors


def validate_log(run_root: Path) -> list[str]:
    """Validate every event in both logs plus policy checks. Empty list means valid."""
    errors: list[str] = []
    timeline = read_log(run_root, "timeline")
    for ev in timeline:
        errors += validate_timeline_event(ev, run_root, "timeline")
    for ev in read_log(run_root, "traces"):
        errors += validate_trace_event(ev, run_root, "traces")
    errors += _policy_checks(timeline, run_root)
    return errors


# ---------------------------------------------------------------------------
# State modeling (shared with render.py)
# ---------------------------------------------------------------------------

MISSION_PHASES = [
    "proposed", "admitted", "planning", "plan_frozen",
    "executing", "analyzing", "reviewing", "committed",
]
_PHASE_BY_TYPE = {
    "mission_proposal": 0,
    "mission_admit": 1,
    "challenge": 2,
    "test_plan": 3,
    "tool_run": 4,
    "observation": 5,
    "review": 6,
    "mission_report": 7,
}
_TERMINAL_PHASES = {"committed", "blocked", "rejected", "cancelled"}


def mission_phase(events: list[dict], mission_id: str) -> str:
    """Infer the mission phase from the event types recorded so far."""
    idx = 0
    for ev in events:
        if ev.get("mission_id") != mission_id:
            continue
        if ev.get("type") == "decision":
            content = ev.get("content") or {}
            terminal = content.get("terminal") or (
                ev.get("status") if ev.get("status") in _TERMINAL_PHASES else None
            )
            if terminal in _TERMINAL_PHASES:
                return terminal
        step = _PHASE_BY_TYPE.get(ev.get("type"))
        if step is not None and step > idx:
            idx = step
    return MISSION_PHASES[idx]


def build_model(run_root: Path) -> dict:
    """Replay both logs into the in-memory model shared by rendering and checkpoints."""
    timeline = read_log(run_root, "timeline")
    traces = read_log(run_root, "traces")
    timeline.sort(key=lambda e: e.get("created_at", ""))
    traces.sort(key=lambda e: e.get("created_at", ""))

    campaign = {"id": run_root.name, "objective": "", "status": "initializing", "created_at": ""}
    for ev in timeline:
        if ev.get("type") == "campaign_init":
            campaign = {
                "id": ev.get("content", {}).get("campaign_id") or run_root.name,
                "objective": (ev.get("content") or {}).get("objective", ""),
                "status": ev.get("status", "active"),
                "created_at": ev.get("created_at", ""),
            }

    missions: dict[str, dict] = {}
    last_mission_id = None
    for ev in timeline:
        mid = ev.get("mission_id")
        if mid:
            last_mission_id = mid
            missions.setdefault(mid, {"id": mid, "question": "", "created_at": ev.get("created_at", "")})
    for ev in timeline:
        mid = ev.get("mission_id")
        if not mid:
            continue
        missions[mid]["created_at"] = min(
            missions[mid].get("created_at") or ev.get("created_at", ""),
            ev.get("created_at", ""),
        )
        if ev.get("type") == "mission_proposal" and not missions[mid]["question"]:
            missions[mid]["question"] = (ev.get("content") or {}).get("research_question", "")
    for mid, mission in missions.items():
        mission["phase"] = mission_phase(timeline, mid)

    hypotheses: dict[str, dict] = {}
    for ev in timeline:
        if ev.get("type") != "hypothesis":
            continue
        content = ev.get("content") or {}
        hid = content.get("hypothesis_id")
        if not hid:
            continue
        h = hypotheses.setdefault(hid, {"id": hid, "versions": [], "mission_id": ev.get("mission_id")})
        h["versions"].append(
            {
                "event_id": ev["id"],
                "created_at": ev.get("created_at"),
                "operation": content.get("operation"),
                "claim": content.get("claim", ""),
                "status": content.get("status"),
                "assessment": content.get("assessment", "unassessed"),
                "change_summary": content.get("change_summary", ""),
                "narrative": content.get("narrative", ""),
                "predictions": content.get("predictions") or [],
                "falsifiers": content.get("falsifiers") or [],
                "scope": content.get("scope") or [],
                "replies_to": ev.get("replies_to"),
                "role": ev.get("role"),
                "reviewed_in": content.get("reviewed_in") or [],
            }
        )
    for h in hypotheses.values():
        h["versions"].sort(key=lambda v: v.get("created_at", ""))
        latest = h["versions"][-1]
        h["claim"] = latest["claim"]
        h["assessment"] = latest["assessment"]
        h["status"] = latest["status"] or "active"
        h["operation"] = latest["operation"]

    evidence: dict[str, dict] = {}
    for ev in timeline:
        if ev.get("type") not in {"evidence_candidate", "review"}:
            continue
        content = ev.get("content") or {}
        if ev.get("type") == "evidence_candidate":
            eid = content.get("evidence_id") or new_id("EVD")
            evidence.setdefault(
                eid,
                {
                    "id": eid,
                    "hypothesis_id": content.get("hypothesis_id"),
                    "direction": content.get("direction"),  # support|challenge|mixed
                    "summary": ev.get("summary", ""),
                    "narrative": content.get("narrative", ""),
                    "mission_id": ev.get("mission_id"),
                    "event_id": ev["id"],
                    "verdict": None,
                    "verdict_reason": "",
                    "review_role": None,
                },
            )
        else:  # review
            eid = content.get("evidence_id")
            if eid and eid in evidence:
                evidence[eid]["verdict"] = content.get("verdict")
                evidence[eid]["verdict_reason"] = content.get("reasons", "")
                evidence[eid]["review_role"] = ev.get("role")

    decisions = [
        {
            "id": ev["id"],
            "created_at": ev.get("created_at"),
            "summary": ev.get("summary", ""),
            "content": ev.get("content") or {},
        }
        for ev in timeline
        if ev.get("type") == "decision"
    ]

    mission_reports = [
        {
            "id": ev["id"],
            "created_at": ev.get("created_at"),
            "mission_id": ev.get("mission_id"),
            "summary": ev.get("summary", ""),
            "content": ev.get("content") or {},
            "role": ev.get("role"),
        }
        for ev in timeline
        if ev.get("type") == "mission_report"
    ]

    tasks: dict[str, dict] = {}
    for ev in traces:
        tid = ev.get("task_id")
        if not tid:
            continue
        t = tasks.setdefault(tid, {"id": tid, "role": "", "events": [], "start": "", "end": ""})
        if ev.get("role"):
            t["role"] = ev["role"]
        if ev.get("kind") == "task_start" and not t["start"]:
            t["start"] = ev.get("created_at", "")
        if ev.get("kind") == "task_end":
            t["end"] = ev.get("created_at", "")
        t["events"].append(ev)
    for t in tasks.values():
        t["events"].sort(key=lambda e: e.get("created_at", ""))

    return {
        "campaign": campaign,
        "missions": missions,
        "hypotheses": hypotheses,
        "evidence": evidence,
        "decisions": decisions,
        "mission_reports": mission_reports,
        "tasks": tasks,
        "timeline": timeline,
        "traces": traces,
        "last_mission_id": last_mission_id,
    }


# ---------------------------------------------------------------------------
# Checkpoints and restore
# ---------------------------------------------------------------------------

def write_checkpoint(run_root: Path, model: dict | None = None) -> dict:
    """Write a checkpoint: state snapshot plus sha256/line counts of both logs.

    The checkpoint event is appended before the hashes are computed so the recorded
    hashes describe the log state after the final write, allowing direct comparison
    at restore time.
    """
    model = model or build_model(run_root)
    chk_id = new_id("CHK")
    append_event(run_root, "timeline", {
        "type": "checkpoint",
        "summary": (
            f"Created checkpoint {chk_id} "
            f"(timeline {log_metrics(run_root, 'timeline')['lines']} lines / "
            f"traces {log_metrics(run_root, 'traces')['lines']} lines)"
        ),
        "role": "director",
    })
    timeline_m = log_metrics(run_root, "timeline")
    traces_m = log_metrics(run_root, "traces")
    checkpoint = {
        "schema": "checkpoint/1",
        "id": chk_id,
        "created_at": now_iso(),
        "timeline": timeline_m,
        "traces": traces_m,
        "state": {
            "campaign_status": model["campaign"]["status"],
            "missions": {mid: {"phase": m["phase"]} for mid, m in model["missions"].items()},
            "hypotheses": {
                hid: {"assessment": h["assessment"], "versions": len(h["versions"])}
                for hid, h in model["hypotheses"].items()
            },
            "evidence": {
                eid: {"verdict": e["verdict"]} for eid, e in model["evidence"].items()
            },
        },
    }
    ck_dir = run_root / "blackboard" / "checkpoints"
    ck_dir.mkdir(parents=True, exist_ok=True)
    ck_path = ck_dir / f"{checkpoint['id']}.json"
    ck_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
    return checkpoint


def validate_checkpoint(run_root: Path, checkpoint_path: Path) -> list[str]:
    """Verify that the logs match the checkpoint sha256/line counts (integrity check)."""
    errors: list[str] = []
    try:
        ck = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"checkpoint file unreadable: {exc}"]
    for kind in ("timeline", "traces"):
        metrics = log_metrics(run_root, kind)
        expected = ck.get(kind, {})
        if metrics["lines"] < expected.get("lines", 0):
            errors.append(f"{kind} has fewer lines than recorded (file truncated?)")
        if expected.get("sha256") and metrics["sha256"] != expected["sha256"]:
            errors.append(f"{kind} sha256 differs from the checkpoint (file modified?)")
    return errors


def restore(run_root: Path, checkpoint_dir: Path) -> dict:
    """Restore from the latest valid checkpoint: verify integrity, then replay the logs."""
    ck_files = sorted(checkpoint_dir.glob("CHK-*.json"))
    if not ck_files:
        return build_model(run_root)
    latest = ck_files[-1]
    errors = validate_checkpoint(run_root, latest)
    if errors:
        raise ValueError(f"checkpoint validation failed ({latest.name}): " + "; ".join(errors))
    return build_model(run_root)


# ---------------------------------------------------------------------------
# Configuration snapshot
# ---------------------------------------------------------------------------

def snapshot_config(run_root: Path, config: dict) -> None:
    """Write the resolved run configuration as an immutable snapshot at the run root."""
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "config.snapshot.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Task progress import
# ---------------------------------------------------------------------------

PROGRESS_KINDS = {"attempt_start", "attempt_end", "tool_run", "status_change"}


def import_progress(run_root: Path, task_id: str, role: str, workspace: Path | None = None) -> int:
    """Import a task's workspace/progress.jsonl into traces.jsonl as trace events.

    Each progress line is {"kind", "summary", "content", "ts"} with kind in
    PROGRESS_KINDS. Returns the number of trace events appended. The original
    timestamp (if any) is preserved as content.progress_ts.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    ws = workspace or (run_root / "tasks" / task_id / "workspace")
    path = ws / "progress.jsonl"
    if not path.is_file():
        return 0
    # Incremental import: track how many physical lines have already been imported.
    offset_path = ws / ".progress.imported"
    offset = 0
    if offset_path.is_file():
        try:
            offset = int(offset_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            offset = 0
    with path.open("r", encoding="utf-8") as handle:
        lines = handle.readlines()
    appended = 0
    for idx in range(offset, len(lines)):
        line_no = idx + 1
        line = lines[idx].strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_no} JSON parse failed: {exc}") from exc
        kind = item.get("kind")
        if kind not in PROGRESS_KINDS:
            raise ValueError(f"{path.name}:{line_no} invalid progress kind: {kind}")
        summary = item.get("summary")
        if not summary or not str(summary).strip():
            raise ValueError(f"{path.name}:{line_no} progress entry missing summary")
        content = item.get("content") or {}
        if not isinstance(content, dict):
            raise ValueError(f"{path.name}:{line_no} progress content must be an object")
        content = dict(content)
        if item.get("ts"):
            content.setdefault("progress_ts", item["ts"])
        append_event(
            run_root,
            "traces",
            {
                "task_id": task_id,
                "role": role,
                "kind": kind,
                "summary": str(summary).strip(),
                "content": content,
            },
        )
        appended += 1
    if appended or len(lines) > offset:
        offset_path.write_text(str(len(lines)), encoding="utf-8")
    return appended


# ---------------------------------------------------------------------------
# Experience library (engineering knowledge, campaign-scoped)
# ---------------------------------------------------------------------------

EXPERIENCE_CATEGORIES = {"env", "tool", "script", "workflow", "pitfall"}


def experience_path(run_root: Path) -> Path:
    return run_root / "experience" / "experience.jsonl"


def experience_list(run_root: Path) -> list[dict]:
    """Read all experience entries. Return [] when the file is missing or empty."""
    path = experience_path(run_root)
    if not path.is_file():
        return []
    entries: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_no} JSON parse failed: {exc}") from exc
    return entries


def experience_add(
    run_root: Path,
    category: str,
    summary: str,
    detail: str = "",
    source_role: str = "",
    source_task: str = "",
) -> str | None:
    """Append one experience entry. Returns the new id, or None when a duplicate summary exists."""
    if category not in EXPERIENCE_CATEGORIES:
        raise ValueError(f"invalid experience category: {category}")
    summary = summary.strip()
    if not summary:
        raise ValueError("experience summary must not be empty")
    for entry in experience_list(run_root):
        if entry.get("summary") == summary:
            return None  # dedupe on summary
    entry = {
        "id": new_id("EXP"),
        "category": category,
        "summary": summary,
        "detail": detail.strip(),
        "source_role": source_role.strip(),
        "source_task": source_task.strip(),
        "created_at": now_iso(),
    }
    path = experience_path(run_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry["id"]


def experience_import(
    run_root: Path,
    delivery_file: Path,
    source_role: str = "",
    source_task: str = "",
) -> int:
    """Import payload.lessons from a subagent delivery.json into the experience library.

    Returns the number of new entries appended (duplicates are skipped).
    """
    data = json.loads(delivery_file.read_text(encoding="utf-8"))
    payload = data.get("payload")
    lessons = []
    if isinstance(payload, dict):
        lessons = payload.get("lessons") or []
    elif isinstance(payload, list):
        # Roles with list payloads (e.g. investigator) may attach lessons per item.
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("lessons"), list):
                lessons += item["lessons"]
    if not lessons and isinstance(data.get("lessons"), list):
        # Tolerate a top-level "lessons" key (schema drift); do not silently drop lessons.
        lessons = data["lessons"]
    if not isinstance(lessons, list):
        raise ValueError("delivery payload.lessons must be a list")
    added = 0
    for lesson in lessons:
        if not isinstance(lesson, dict):
            raise ValueError("each lesson must be an object with category/summary/detail")
        if experience_add(
            run_root,
            category=lesson.get("category", ""),
            summary=lesson.get("summary", ""),
            detail=lesson.get("detail", ""),
            source_role=source_role or lesson.get("source_role", ""),
            source_task=source_task or lesson.get("source_task", ""),
        ):
            added += 1
    return added


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Event and trace log utilities")
    parser.add_argument("run_root", help="run root directory")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="validate both logs")
    sub.add_parser("model", help="print the state model summary")
    sub.add_parser("checkpoint", help="write a checkpoint")
    p_replay = sub.add_parser("replay", help="replay the logs and print the JSON model")
    p_replay.add_argument("--out")
    p_import = sub.add_parser(
        "import-progress",
        help="import a task's workspace/progress.jsonl as trace events",
    )
    p_import.add_argument("--task", required=True, help="task id (TSK-...)")
    p_import.add_argument("--role", required=True, help="role of the task owner")
    p_import.add_argument(
        "--workspace",
        help="workspace dir override (default <run_root>/tasks/<task>/workspace)",
    )
    p_exp = sub.add_parser(
        "experience-add",
        help="append one engineering-experience entry (dedup by summary)",
    )
    p_exp.add_argument("--category", required=True, choices=sorted(EXPERIENCE_CATEGORIES))
    p_exp.add_argument("--summary", required=True)
    p_exp.add_argument("--detail", default="")
    p_exp.add_argument("--source-role", default="")
    p_exp.add_argument("--source-task", default="")
    p_expimp = sub.add_parser(
        "experience-import",
        help="import payload.lessons from a subagent delivery.json",
    )
    p_expimp.add_argument("--delivery", required=True, help="path to delivery.json")
    p_expimp.add_argument("--source-role", default="")
    p_expimp.add_argument("--source-task", default="")
    p_expl = sub.add_parser("experience-list", help="list experience entries as JSON")

    args = parser.parse_args()
    root = Path(args.run_root).resolve()

    if args.cmd == "validate":
        errors = validate_log(root)
        if errors:
            print("Validation failed:")
            for e in errors:
                print("  - " + e)
            return 1
        print("Validation passed")
        return 0
    if args.cmd == "model":
        model = build_model(root)
        print(json.dumps(
            {
                "campaign": model["campaign"],
                "missions": {k: {"phase": v["phase"]} for k, v in model["missions"].items()},
                "hypotheses": {k: {"assessment": v["assessment"], "versions": len(v["versions"])} for k, v in model["hypotheses"].items()},
                "evidence": {k: v["verdict"] for k, v in model["evidence"].items()},
                "mission_reports": [{"id": r["id"], "verdict": (r["content"] or {}).get("mission_verdict")} for r in model["mission_reports"]],
                "tasks": {k: {"role": v["role"], "events": len(v["events"])} for k, v in model["tasks"].items()},
            },
            ensure_ascii=False, indent=2,
        ))
        return 0
    if args.cmd == "checkpoint":
        ck = write_checkpoint(root)
        print(f"checkpoint {ck['id']} written")
        return 0
    if args.cmd == "replay":
        model = build_model(root)
        payload = json.dumps(model, ensure_ascii=False, indent=2, default=str)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        else:
            print(payload)
        return 0
    if args.cmd == "import-progress":
        try:
            count = import_progress(
                root,
                task_id=args.task,
                role=args.role,
                workspace=Path(args.workspace).resolve() if args.workspace else None,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Imported {count} progress entries as trace events")
        return 0
    if args.cmd == "experience-add":
        try:
            eid = experience_add(
                root,
                category=args.category,
                summary=args.summary,
                detail=args.detail,
                source_role=args.source_role,
                source_task=args.source_task,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Added experience entry {eid}" if eid else "Duplicate summary; skipped")
        return 0
    if args.cmd == "experience-import":
        try:
            added = experience_import(
                root,
                delivery_file=Path(args.delivery).resolve(),
                source_role=args.source_role,
                source_task=args.source_task,
            )
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Imported {added} experience entries (duplicates skipped)")
        return 0
    if args.cmd == "experience-list":
        print(json.dumps(experience_list(root), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_cli())