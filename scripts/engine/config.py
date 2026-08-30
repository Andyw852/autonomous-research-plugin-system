"""Plugin configuration loading.

The plugin is deliberately harness-agnostic. Paths in the YAML are resolved
relative to the plugin root, not the current working directory.
"""
from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


DEFAULT_CONFIG_NAME = "config/plugin.config.yaml"


@dataclasses.dataclass
class PluginConfig:
    root: Path
    name: str
    agents_dir: Path
    blackboard_scripts_dir: Path
    run_root: Path
    subagent_backend: str
    language: str
    max_outer_rounds: int
    max_inner_rounds: int
    min_hypotheses: int
    max_hypotheses: int
    propose_count: int
    min_outer_rounds: int
    closure_mode: str
    require_boundary_extension_resolution: bool
    network_policy: str
    auto_rebuild: str
    trace_enabled: bool

    @classmethod
    def from_dict(cls, root: Path, data: dict[str, Any]) -> "PluginConfig":
        root = root.resolve()
        plugin = data.get("plugin", {})
        agents_dir = root / plugin.get("agents_dir", "agents")
        bbs = root / plugin.get(
            "blackboard_scripts_dir",
            "scripts/engine/blackboard_core",
        )
        engine_cfg = data.get("engine", {})
        mission_cfg = data.get("mission", {})
        director_cfg = data.get("director", {})
        return cls(
            root=root,
            name=plugin.get("name", "autonomous-research-engine"),
            agents_dir=agents_dir,
            blackboard_scripts_dir=bbs,
            run_root=root / data.get("run_root", "runs"),
            subagent_backend=data.get("subagent_backend", {}).get("default", "auto"),
            language=engine_cfg.get("language", "en"),
            max_outer_rounds=int(engine_cfg.get("max_outer_rounds", 10)),
            max_inner_rounds=int(mission_cfg.get("max_inner_rounds", engine_cfg.get("max_inner_rounds", 3))),
            min_hypotheses=int(mission_cfg.get("min_hypotheses", 1)),
            max_hypotheses=int(mission_cfg.get("max_hypotheses", 5)),
            propose_count=int(engine_cfg.get("propose_count", 1)),
            min_outer_rounds=int(director_cfg.get("min_outer_rounds", 0)),
            closure_mode=str(director_cfg.get("closure_mode", "normal")),
            require_boundary_extension_resolution=bool(
                director_cfg.get("require_boundary_extension_resolution", False)
            ),
            network_policy=engine_cfg.get("network_policy", "deny"),
            auto_rebuild=engine_cfg.get("auto_rebuild", "after_each_event"),
            trace_enabled=bool(data.get("trace", {}).get("enabled", True)),
        )


def find_plugin_root(start: Path | None = None) -> Path:
    """Find the directory that contains config/plugin.config.yaml."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / DEFAULT_CONFIG_NAME).is_file():
            return candidate
    raise FileNotFoundError(f"Could not find {DEFAULT_CONFIG_NAME} from {current}")


def load_config(path: Path | str | None = None) -> PluginConfig:
    """Load plugin config. If path is None, search upward from CWD."""
    if path is None:
        path = find_plugin_root() / DEFAULT_CONFIG_NAME
    path = Path(path).resolve()
    root = path.parent.parent
    if yaml is None:
        raise RuntimeError("PyYAML is required to load plugin config")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return PluginConfig.from_dict(root, data)
