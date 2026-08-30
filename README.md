# Autonomous Research Engine Plugin

A harness-independent, SKILL-packaged deterministic multi-agent research engine.

The default Campaign end product is a mechanism-level scientific law plus the
candidate shortlist it recommends. A shortlist-only completion is an
`operational_stop`, not `scientific_closure`.


- `AGENTS.md` is the file the main agent should read. It contains the operating
  instructions for running research campaigns.
- `contracts/protocol.md` is the formal behavior contract (logs, event types,
  scientific norms, blackboard semantics).
- `docs/autonomous-research-reference.md` is a concise protocol quick reference.
- `scripts/engine/blackboard_core/` is the engine-internal blackboard implementation.
- `skills/` contains pluggable computational capabilities:
  - `cofkit/`
  - `pytdc/`
  - `rdkit/`
  - `long-running-task/` (generic execution pattern)
- `domains/` contains optional domain cards. A domain card frames which scientific
  questions are worth asking inside the DDM-supported space; it is not a SKILL and
  its absence never blocks a campaign.
- Artifacts from every task are preserved under `runs/<CAM>/artifacts/<mission>/<task>/`
  and referenced from events with sha256.

## Quick start

```bash
python3 -m unittest discover -s scripts/tests -v
python3 scripts/smoke_main_agent.py
```

## Engine commands

```bash
# init creates a new campaign folder under the configured run root,
# e.g. runs/<CAM-ULID>/; it never writes directly into the base runs/ directory.
python3 -m scripts.engine.cli init --objective "Research objective"
python3 -m scripts.engine.cli snapshot
python3 -m scripts.engine.cli status
python3 -m scripts.engine.cli validate
python3 -m scripts.engine.cli smoke
python3 -m scripts.engine.cli propose --round 1 --proposal proposal.json
python3 -m scripts.engine.cli consume-directives
python3 -m scripts.engine.cli admit-mission --mission MIS-...
python3 -m scripts.engine.cli next --mission MIS-...
python3 -m scripts.engine.cli submit-delivery --task TSK-...
python3 -m scripts.engine.cli sync-progress --task TSK-...
```

These commands are the engine's protocol/development interface. They are used by
the main agent internally, by automated tests, and for manual debugging.

## Main-agent usage

See `AGENTS.md` for the full main-agent instructions. In short:

1. Load this folder into a harness that supports a main agent and subagents.
2. Give the main agent a natural-language research task.
3. The main agent acts as Director, calls `next`, creates subagents, submits
   deliveries, and continues until a terminal decision.

## Multi-mission support

- Multiple Missions can coexist in the same run and be advanced in an interleaved
  way by calling `next` with different `MIS-...` ids.
- The engine does **not** yet provide an automatic parallel mission scheduler.
  If you need true concurrent Missions, the current safe pattern is to create
  multiple Missions and let the main agent interleave subagent creation/submission.
