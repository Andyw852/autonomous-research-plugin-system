---
name: long-running-task
description: Generic pattern for executing tasks that may exceed a single tool-call timeout. Use when a subagent must run long computations, batch jobs, simulations, training, or any work that can take minutes to hours. The skill provides a detached launcher + status/done file + polling pattern that keeps the subagent alive and makes progress observable.
license: MIT
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.0"
  skill-author: autonomous-research-plugin-system
  compatibility: POSIX shell, Python 3, no extra dependencies
---

# Long-Running Task Pattern

## When to use

Use this skill when a task may take longer than a single foreground tool call
can safely wait, for example:

- long GCMC / molecular simulation
- LAMMPS optimization or MD
- large batch screening
- model training or inference
- data processing over many files
- any external command expected to run for minutes to hours

## Core pattern

1. **Wrap the real work in a driver script** so the work is independent of the
   interactive shell and can be launched once.
2. **Launch the driver detached** with `setsid nohup`, writing stdout/stderr to
   a log file and recording the PID.
3. **The driver writes progress** to a JSON status file (`status.json`) and, on
   completion, creates a `done.flag`.
4. **The subagent stays alive and polls** with short bash commands:
   - `ps` to see the process
   - `cat status.json` to see progress
   - `test -f done.flag` to detect completion
5. **After `done.flag` appears**, collect outputs and deliver normally.

## Why this pattern

- A single foreground long command can exceed the tool-call timeout and be
  killed.
- A plain `nohup ... &` may still die when the launching subagent session ends.
- The reliable in-session pattern is:

  ```text
  setsid nohup start + keep the launching subagent alive + poll status/done files
  ```

- If work must survive beyond the subagent/session entirely, use an external
  scheduler or process supervisor instead:

  ```text
  SLURM / tmux / screen / systemd-run / external queue
  ```

## Files in this skill

- `scripts/run_long_task.sh` — generic detached launcher template
- `scripts/long_task_driver.py` — generic driver skeleton (fill in tasks)
- `scripts/poll_status.sh` — generic polling loop template
- `scripts/status.example.json` — example status file shape

## Usage notes

- The scripts are **templates**, not necessarily directly runnable. Fill in the
  task list, commands, parameters, and output paths before use.
- Keep the driver idempotent when possible: skip already-completed tasks.
- Use a lock file or atomic writes when multiple workers update the same status
  file.
- Record the launch PID and log paths so the subagent can inspect failures.
- Do not hide the fact that work is still running: report partial progress and
  explicitly note any unfinished work in the delivery.
