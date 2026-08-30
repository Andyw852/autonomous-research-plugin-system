"""Core data models used by the deterministic engine."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any


@dataclasses.dataclass
class Brief:
    role: str
    task_id: str
    mission_id: str | None
    content: dict[str, Any]
    workspace: Path
    context: dict[str, Any] = dataclasses.field(default_factory=dict)
    experience_entries: list[dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Delivery:
    task_id: str
    role: str
    status: str
    payload: Any
    delivery_md: str
    delivery_json_path: Path
    lessons: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    progress_path: Path | None = None


@dataclasses.dataclass
class Task:
    id: str
    role: str
    workspace: Path
    mission_id: str | None = None
    status: str = "created"
    brief: Brief | None = None
    delivery: Delivery | None = None


@dataclasses.dataclass
class Mission:
    id: str
    status: str = "proposed"
    inner_round: int = 0
    current_phase: str | None = None
    tasks: dict[str, Task] = dataclasses.field(default_factory=dict)
