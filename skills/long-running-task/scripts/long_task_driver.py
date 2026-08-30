#!/usr/bin/env python3
"""Generic long-running task driver skeleton.

Fill in the concrete task list, command builder, status updates, and done flag.
The structure below is intentionally generic.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

# TODO: set the actual workspace root.
WS = Path(__file__).resolve().parent
STATUS_FILE = WS / "status.json"
DONE_FLAG = WS / "done.flag"
LOG_DIR = WS / "logs"
LOG_DIR.mkdir(exist_ok=True)

# TODO: define the actual task list. Each item should be enough to build one
# command or one callable unit.
TASKS = [
    # {"id": "task-1", "command": ["echo", "hello"]},
    # {"id": "task-2", "command": ["python3", "run_one.py", "--input", "x"]},
]

# TODO: set the concurrency level appropriate for the machine.
PARALLELISM = 4


def log_run(entry: dict) -> None:
    path = WS / "tool_runs.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_status(task_id: str, status: str, **fields) -> None:
    data = {}
    if STATUS_FILE.exists():
        data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    data.setdefault("jobs", {})
    data["jobs"][task_id] = {
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        **fields,
    }
    STATUS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def run_one(task: dict) -> bool:
    task_id = task["id"]
    command = task["command"]
    update_status(task_id, "running")
    started = time.time()
    try:
        result = subprocess.run(command, cwd=WS, capture_output=True, text=True, timeout=24 * 3600)
        ok = result.returncode == 0
        update_status(task_id, "succeeded" if ok else "failed", exit_code=result.returncode,
                      wall_seconds=round(time.time() - started, 2))
        log_run({"id": task_id, "status": "succeeded" if ok else "failed",
                 "exit_code": result.returncode, "wall_seconds": round(time.time() - started, 2)})
        return ok
    except Exception as exc:
        update_status(task_id, "failed", error=str(exc))
        log_run({"id": task_id, "status": "failed", "error": str(exc)})
        return False


def main() -> None:
    # TODO: initialize status file with total count if needed.
    results = []
    index = 0
    pending = list(TASKS)
    while pending:
        batch = pending[:PARALLELISM]
        pending = pending[PARALLELISM:]
        # TODO: implement a real bounded worker pool or use ThreadPoolExecutor.
        for task in batch:
            results.append((task["id"], run_one(task)))

    # TODO: write final summary / done flag.
    DONE_FLAG.write_text("ALL_TASKS_ATTEMPTED\n", encoding="utf-8")


if __name__ == "__main__":
    main()
