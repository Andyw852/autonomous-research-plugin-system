---
name: autonomous-research
description: Protocol-level reference for the deterministic autonomous research engine.
---

# Autonomous Research Protocol Reference

This document is a concise protocol reference. The main agent's operating instructions
are in `AGENTS.md`; the full formal contract is in `contracts/protocol.md`.

## Architecture

- **Main agent = Director / research-program manager**: chooses research questions,
  scope, resources, and whether to continue, extend, or close a campaign; creates
  subagents.
- **Deterministic engine = `scripts/engine`**: owns state machines, validation,
  blackboard writes, checkpoints, and returns `awaiting_subagent` / `gate` /
  `complete` actions.
- **Scientific subagents**: created by the main agent; write `delivery.json` +
  `delivery.md` in their workspace.
- **Direction Reviewer**: a fresh subagent that audits the Director's Mission
  proposals, next-direction choices, and terminal decisions before commitment.

## Research philosophy

- **P0 Research universe**: study only states, properties, and perturbations that
  the available computational SKILLs declare as supported (`U_DDM`).
- **P1 Computable mechanism first**: every hypothesis states a mechanism as
  `variable -> computable descriptor(s) -> simulated property -> direction`.
- **P2 DDM as a reliable virtual instrument**: one protocol is one reproducible
  instrument; fixed-seed reruns are not independent physical replicates.
- **P3 Space before precision**: map orthogonal DDM-supported design axes before
  increasing precision on any single system.
- **P4 Contrast before correlation**: single-variable controlled contrasts decide
  between mechanisms; descriptor correlations only suggest them.
- **P5 Decision-graded evidence**: screening-grade, discrimination-grade, or
  confirmation-grade. Method grade shall match decision grade, and every
  computation shall change a named scientific decision.

## Law maturity

- Law candidates progress through `lead`, `rule_candidate`, `rule`, and `law`.
- Each mission report updates the law-quality ledger and research frontier.
- In strict mode, `scientific_closure` requires `maturity == "law"` and no pending
  high- or medium-priority frontier.

## Dual loop

- Outer loop: Director reads snapshot → proposes Mission(s) → engine admits and runs
  inner loop → mission-synthesizer reports → Director decides whether to continue.
- Inner loop: per Mission, repeated up to `mission.max_inner_rounds`:
  hypothesize → challenge → revise (if needed) → design → freeze → execute →
  analyze → review → decide → commit.
- After the inner rounds finish, the mission-synthesizer produces a `mission_report`.

## Completion rules

- A Mission is complete only after a `mission_report` exists.
- A Campaign is complete only after a terminal `decision` exists.
- Do not stop after candidates; finish the current Mission's synthesis and then
  make an explicit Director decision. A shortlist-only completion is an
  `operational_stop`, not `scientific_closure`.

## Closure readiness

- `scientific_closure` is blocked until:
  - no incomplete missions;
  - no pending tasks;
  - every open question has a disposition: `resolved`, `out_of_scope`, or
    `deferred`;
  - the configured `min_outer_rounds` has been reached;
  - every feasible `boundary_extension_candidates` entry has a final disposition:
    `accepted_for_mission`, `rejected_scientific`, or `user_override`;
  - the final law carries a law-quality ledger with `maturity == "law"`, all
    criteria `pass` or `not_applicable`, and no pending high- or medium-priority
    research frontier;
  - a divergence review has been recorded in `final_law.divergence_review`.

## Boundary extension

- A well-bounded law is a valid scientific result and a candidate for further
  generalization, not necessarily a terminal result.
- Before closure, every feasible `boundary_extension_candidates` entry must be
  resolved: accepted for a new Mission, rejected on scientific grounds, or
  explicitly overridden by the user. `deferred` alone is not a closure disposition.
- If a feasible candidate remains pending, the Director must open a
  boundary-extension Mission before closure.
- Mission proposals define research questions, scope, non-goals, success criteria,
  and available capabilities; they do not prescribe concrete hypotheses.

## Divergence review

- Before closure, the Director must record a divergence review in
  `final_law.divergence_review`.
- It asks whether a fundamentally different perspective is testable and could
  create new scientific value even if it does not overturn the current law.
- If the decision is `open_mission`, closure must not proceed.

## Long-running computation

- High-value exploration must not be suppressed solely because it is expensive,
  and expensive work shall not be added solely because resources are available.
- Every computation shall pass the decision-value gate.
- Use timeouts, checkpoints, staged execution, and explicit resource plans.
- Multi-seed production runs are confirmation-grade tools and shall not be used
  for screening-grade questions before a shortlist exists.
- The Experiment Runner shall use `skills/long-running-task/SKILL.md` for tasks
  that may exceed a single tool-call timeout.


## Key rules

- Freeze before execution: test plans are drafts (`frozen: false`) from the Test
  Designer; the engine freezes them before the Experiment Runner executes.
- Independence: hypothesis authors do not review their own evidence; runners do not
  review their own results.
- Only Experiment Runner may execute computational skills.
- DDM computational skills are automatically discovered from `skills/` and
  selected by the Director for the Mission; role-specific execution patterns and
  reference skills are declared in each role's `Skills` section.
- Optional `domains/<topic>/DOMAIN.md` cards may be attached to briefs; their
  absence never blocks a campaign.
- Preserve negative, failed, rejected, and inconclusive records.
