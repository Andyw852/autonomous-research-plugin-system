#!/usr/bin/env bash
#
# Generic detached launcher template.
#
# Launch the real driver detached from the current session:
#
#   nohup setsid bash run_long_task.sh \
#     > logs/launcher.stdout 2>&1 &
#   echo $! > task.pid
#
# The subagent should then stay alive and poll status.json / done.flag.
set -u

# TODO: set the actual working directory / task workspace.
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$WS/logs"
STATUS_FILE="$WS/status.json"
DONE_FLAG="$WS/done.flag"

mkdir -p "$LOGS"

# TODO: set the actual driver command.
DRIVER=(python3 "$WS/long_task_driver.py")

# TODO: set any environment variables needed by the driver.
export SOME_VAR="value"

echo "[$(date -Is)] launcher started" > "$LOGS/launcher.stdout"
echo "[$(date -Is)] launching driver" >> "$LOGS/launcher.stdout"

# Launch the driver in the background and wait for it inside this detached
# launcher. The launcher itself is started with setsid nohup, so this process
# tree survives the interactive shell.
"${DRIVER[@]}" >> "$LOGS/launcher.stdout" 2>&1
rc=$?

echo "[$(date -Is)] driver exited rc=$rc" >> "$LOGS/launcher.stdout"

# TODO: write done.flag with the final status.
: > "$DONE_FLAG"
echo "ALL_TASKS_ATTEMPTED" > "$DONE_FLAG"
exit "$rc"
