"""Trace helpers used by the engine."""
from __future__ import annotations

from typing import Any

from .blackboard import Blackboard


def task_start(blackboard: Blackboard, task_id: str, role: str, content: dict[str, Any] | None = None) -> str:
    event_id, _ = blackboard.append_trace(
        {
            "kind": "task_start",
            "task_id": task_id,
            "role": role,
            "summary": f"The {role} task started.",
            "content": content or {},
        }
    )
    return event_id


def brief_sent(blackboard: Blackboard, task_id: str, role: str, content: dict[str, Any] | None = None) -> str:
    event_id, _ = blackboard.append_trace(
        {
            "kind": "brief_sent",
            "task_id": task_id,
            "role": role,
            "summary": f"The brief was sent to the {role} subagent.",
            "content": content or {},
        }
    )
    return event_id


def delivery_received(blackboard: Blackboard, task_id: str, role: str, content: dict[str, Any] | None = None) -> str:
    event_id, _ = blackboard.append_trace(
        {
            "kind": "delivery_received",
            "task_id": task_id,
            "role": role,
            "summary": f"The {role} delivery was received.",
            "content": content or {},
        }
    )
    return event_id


def task_end(blackboard: Blackboard, task_id: str, role: str, content: dict[str, Any] | None = None) -> str:
    event_id, _ = blackboard.append_trace(
        {
            "kind": "task_end",
            "task_id": task_id,
            "role": role,
            "summary": f"The {role} task ended.",
            "content": content or {},
        }
    )
    return event_id
