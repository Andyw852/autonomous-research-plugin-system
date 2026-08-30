"""Deterministic multi-agent research engine (SKILL-packaged plugin)."""

__all__ = [
    "ProtocolEngine",
    "SubagentBackend",
    "FakeSubagentBackend",
    "load_config",
]

from .config import load_config
from .protocol import ProtocolEngine
from .subagents import FakeSubagentBackend, SubagentBackend
