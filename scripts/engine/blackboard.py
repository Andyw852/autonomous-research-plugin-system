"""Blackboard adapter.

This module wraps the engine-internal blackboard implementation so the plugin can
reuse the proven log/validation/render machinery.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def _load_events_module(scripts_dir: Path):
    """Load events.py from the internal blackboard module."""
    path = Path(scripts_dir) / "events.py"
    if not path.is_file():
        raise FileNotFoundError(f"events.py not found: {path}")
    spec = importlib.util.spec_from_file_location("_blackboard_events", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Blackboard:
    """Thin wrapper around the existing blackboard scripts."""

    def __init__(self, run_root: Path, scripts_dir: Path):
        self.run_root = Path(run_root).resolve()
        self.scripts_dir = Path(scripts_dir).resolve()
        self.events = _load_events_module(self.scripts_dir)
        self.run_root.mkdir(parents=True, exist_ok=True)

    # --- events ---
    def append_timeline(self, event: dict[str, Any]) -> tuple[str, int]:
        return self.events.append_event(self.run_root, "timeline", event)

    def append_trace(self, event: dict[str, Any]) -> tuple[str, int]:
        return self.events.append_event(self.run_root, "traces", event)

    def read_timeline(self) -> list[dict[str, Any]]:
        return self.events.read_log(self.run_root, "timeline")

    def read_traces(self) -> list[dict[str, Any]]:
        return self.events.read_log(self.run_root, "traces")

    def validate(self) -> list[str]:
        return self.events.validate_log(self.run_root)

    def build_model(self) -> dict[str, Any]:
        return self.events.build_model(self.run_root)

    def checkpoint(self) -> dict[str, Any]:
        return self.events.write_checkpoint(self.run_root)

    def snapshot_config(self, config: dict[str, Any]) -> None:
        self.events.snapshot_config(self.run_root, config)

    def import_progress(self, task_id: str, role: str, workspace: Path | None = None) -> int:
        return self.events.import_progress(self.run_root, task_id, role, workspace)

    def sync_progress(self, task_id: str, role: str, workspace: Path | None = None) -> int:
        """Import newly appended progress lines and rebuild views if any were added."""
        count = self.import_progress(task_id, role, workspace)
        if count:
            self.render()
        return count

    def experience_list(self) -> list[dict[str, Any]]:
        return self.events.experience_list(self.run_root)

    def experience_add(self, category: str, summary: str, detail: str, source_role: str, source_task: str = "") -> str:
        return self.events.experience_add(
            self.run_root,
            category=category,
            summary=summary,
            detail=detail,
            source_role=source_role,
            source_task=source_task,
        )

    def experience_import(self, delivery_json: Path, source_role: str, source_task: str) -> int:
        return self.events.experience_import(
            self.run_root,
            delivery_file=delivery_json,
            source_role=source_role,
            source_task=source_task,
        )

    # --- render ---
    def render(self, checkpoint: bool = False) -> list[str]:
        render_script = self.scripts_dir / "render.py"
        if not render_script.is_file():
            raise FileNotFoundError(f"render.py not found: {render_script}")
        # Import render module dynamically; it should expose a main or run_render.
        # Ensure the original scripts dir is importable so render.py can `from events import ...`.
        sys.path.insert(0, str(self.scripts_dir))
        try:
            spec = importlib.util.spec_from_file_location("_blackboard_render", render_script)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        finally:
            try:
                sys.path.remove(str(self.scripts_dir))
            except ValueError:
                pass
        if hasattr(module, "render_all"):
            module.render_all(self.run_root, checkpoint=checkpoint)
        elif hasattr(module, "main"):
            # Many render scripts expose main(argv) or main().
            args = [str(self.run_root)]
            if checkpoint:
                args.append("--checkpoint")
            module.main(args)
        elif hasattr(module, "run"):
            module.run(str(self.run_root), checkpoint=checkpoint)
        else:
            raise RuntimeError(f"render.py has no callable entry: {render_script}")
        return [str(render_script)]
