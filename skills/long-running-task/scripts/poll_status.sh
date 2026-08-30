#!/usr/bin/env bash
#
# Generic polling loop template.
#
# The subagent should stay alive and run this (or equivalent short commands)
# until done.flag appears. Do not use a single foreground call for the whole
# long task.
set -u

# TODO: set the actual task workspace.
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_FILE="$WS/status.json"
DONE_FLAG="$WS/done.flag"

# TODO: set an appropriate poll interval.
POLL_SECONDS=30
# TODO: set an optional overall wait cap, or omit for indefinite polling.
MAX_WAIT_SECONDS=0

started="$(date +%s)"

while [ ! -f "$DONE_FLAG" ]; do
    now="$(date +%s)"
    if [ "$MAX_WAIT_SECONDS" -gt 0 ] && [ $(( now - started )) -ge "$MAX_WAIT_SECONDS" ]; then
        echo "timed out waiting for $DONE_FLAG"
        exit 1
    fi
    echo "--- status $(date -Is) ---"
    if [ -f "$STATUS_FILE" ]; then
        python3 - "$STATUS_FILE" <<'PY'
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text())
jobs = data.get("jobs", {})
summary = {}
for job in jobs.values():
    s = job.get("status", "unknown")
    summary[s] = summary.get(s, 0) + 1
print("summary:", summary)
print("done:", data.get("done", False))
PY
    else
        echo "status file not ready yet"
    fi
    sleep "$POLL_SECONDS"
done

echo "done flag found: $DONE_FLAG"
