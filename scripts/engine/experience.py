"""Experience library helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .blackboard import Blackboard


def relevant_entries(blackboard: Blackboard, role: str, category: str | None = None) -> list[dict[str, Any]]:
    entries = blackboard.experience_list()
    result = []
    for entry in entries:
        if category and entry.get("category") != category:
            continue
        if role:
            source = entry.get("source_role", "")
            applicable = entry.get("roles") or []
            if source != role and role not in applicable:
                continue
        result.append(entry)
    return result


def import_lessons(blackboard: Blackboard, delivery_json: Path, role: str, task_id: str) -> int:
    return blackboard.experience_import(delivery_json, source_role=role, source_task=task_id)
