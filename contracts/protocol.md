# Autonomous Research Protocol

This contract defines the four-layer data model, the two logs, the dual-loop
architecture, role permissions, and scientific norms. The deterministic engine is
the single writer of the logs, checkpoints, and views.

## 1. Four-layer model

1. **Event layer** — `runs/<CAM>/timeline.jsonl`: append-only research events.
2. **Trace layer** — `runs/<CAM>/traces.jsonl`: append-only operational events.
3. **Presentation layer** — `runs/<CAM>/blackboard/`: derived HTML/Markdown views.
4. **Workspace/artifact layer** — `runs/<CAM>/tasks/<TSK>/workspace/` and
   `runs/<CAM>/artifacts/`.

Chat messages are lifecycle notifications only. The two logs are authoritative;
views are rebuildable. Recovery verifies checkpoints against the logs and replays
the logs.

## 2. Dual-loop architecture

### 2.1 Outer loop

The Director runs continuously for a Campaign. It owns scientific direction and
proposes Missions. The default Campaign end product is a **law plus a shortlist**:
a bounded mechanism-level regularity and the candidate set it recommends. A
shortlist-only completion is an `operational_stop`, not `scientific_closure`.

```text
while campaign active and outer budget remains:
    snapshot = engine state + latest mission reports
    Director proposes Missions
    if no worthwhile Mission remains: record decision(no_valuable_mission)
    for each proposal:
        admit Mission
        run the inner loop
        mission-synthesizer appends a mission_report
```

The engine owns protocol mechanics and never produces scientific content.

### 2.2 Inner loop

Each Mission runs a bounded hypothesis-evidence cycle:

```text
hypothesis -> challenge -> revision -> frozen test plan -> execution ->
observation -> evidence candidate -> independent review -> assessment update ->
commit -> mission report
```

The inner loop is performed by the scientific subagents. The Director does not
participate in concrete hypothesis, computation, or evidence review.

### 2.3 Convergence

- Mission Synthesizer judges only whether one Mission converged.
- The Director judges whether another Mission is worthwhile or whether the
  Campaign may terminate.

## 3. Events

Common timeline fields: `schema`, `id` (`EVT-*`), `type`, `mission_id`,
`task_id`, `role`, `status`, `summary`, `content`, `refs[]`, `artifacts[]`,
`replies_to`, `created_at`.

Types: `campaign_init`, `mission_proposal`, `mission_admit`, `hypothesis`,
`challenge`, `test_plan`, `tool_run`, `observation`, `evidence_candidate`,
`review`, `direction_review`, `decision`, `mission_report`, `note`, `checkpoint`.

### 3.1 Research-event semantics

- `hypothesis`: stable `hypothesis_id`, `operation`, `claim`, `status`,
  `assessment`, `predictions`, `falsifiers`, `scope`, `extension_candidates`,
  `change_summary`. Successive events form the hypothesis lineage.
- `challenge`: `target_ids`, `readiness`, `issues`, `boundary_assessment`.
- `test_plan`: `frozen`, `research_move`, `evidence_grade`, `law_quality_gap`,
  `method`, `decision_criteria`, `boundary_probes`. A frozen plan must not be
  rewritten.
- `tool_run`: `tool_name`, `status`, `command`, `artifacts`.
- `observation`: descriptive extraction of raw results.
- `evidence_candidate`: `evidence_id`, `hypothesis_id`, `direction`,
  `evidence_grade`, `law_quality_gap`, `decision_impact`, `narrative`,
  `boundary`.
- `review`: `evidence_id`, `verdict`, `reasons`, `boundary_violation`,
  `evidence_grade`, `scientific_value`, `law_quality_gap`.
- `direction_review`: `target` (`proposal`, `next_direction`, or
  `terminal_decision`), `verdict` (`approve`, `revise`, or `reject`),
  `blocking_issues`, `required_changes`, `law_quality_assessment`,
  `frontier_alignment`, and `capability_gap`. It audits the Director's direction,
  not scientific content.
- `decision`: `text`, `rationale`, terminal status. A `scientific_closure`
  decision additionally carries `final_law`.
- `mission_report`: produced by the Mission Synthesizer and used by the Director
  to update the law candidate and research frontier.

### 3.2 `final_law` schema

```json
{
  "statement": "Mechanism-level regularity statement",
  "final_hypotheses": ["Final supported conclusions"],
  "evidence_support": "Accepted evidence chain",
  "boundaries": "Applicability boundaries and untested scope",
  "recommendation": "Decision-useful final recommendation",
  "law_quality_ledger": {
    "law_candidate": "Current law candidate",
    "maturity": "lead | rule_candidate | rule | law",
    "criteria": {
      "mechanism": "pass | partial | fail | not_applicable",
      "controlled_discrimination": "pass | partial | fail | not_applicable",
      "generality": "pass | partial | fail | not_applicable",
      "boundary_map": "pass | partial | fail | not_applicable",
      "decision_utility": "pass | partial | fail | not_applicable",
      "reproducibility": "pass | partial | fail | not_applicable"
    },
    "gaps": ["Concrete missing evidence or controls"]
  },
  "divergence_review": {
    "alternative_perspective": "A fundamentally different perspective",
    "testable": true,
    "new_scientific_value": "high | medium | low",
    "decision": "open_mission | not_testable | user_override"
  },
  "open_questions": [
    {
      "question": "Residual question",
      "status": "resolved | out_of_scope | deferred",
      "reason": "Why this status is appropriate",
      "boundary_extension": false
    }
  ]
}
```

### 3.3 `mission_report` schema

```json
{
  "type": "mission_report",
  "role": "mission-synthesizer",
  "mission_id": "MIS-...",
  "summary": "One sentence summarizing the Mission outcome",
  "content": {
    "mission_verdict": "converged | inconclusive | not_testable | blocked | mixed",
    "law_quality_ledger": {
      "law_candidate": "Current law candidate",
      "maturity": "lead | rule_candidate | rule | law",
      "criteria": {
        "mechanism": "pass | partial | fail | not_applicable",
        "controlled_discrimination": "pass | partial | fail | not_applicable",
        "generality": "pass | partial | fail | not_applicable",
        "boundary_map": "pass | partial | fail | not_applicable",
        "decision_utility": "pass | partial | fail | not_applicable",
        "reproducibility": "pass | partial | fail | not_applicable"
      },
      "gaps": ["Concrete missing evidence or controls"]
    },
    "research_frontier": [
      {
        "move": "map | contrast | break | generalize | validate | exploit",
        "target_law_candidate": "Law candidate addressed by this frontier",
        "quality_gap": "Ledger criterion or boundary this frontier resolves",
        "expected_decision_change": "Scientific decision this frontier changes",
        "evidence_grade": "screening | discrimination | confirmation",
        "priority": "high | medium | low",
        "disposition": "pending | accepted_for_mission | rejected_scientific | out_of_scope | user_override"
      }
    ],
    "hypothesis_updates": [
      {
        "hypothesis_id": "HYP-...",
        "old_assessment": "unassessed | supported | weakened | mixed | refuted",
        "new_assessment": "unassessed | supported | weakened | mixed | refuted",
        "rationale": "Which accepted evidence drove the change, and the boundary"
      }
    ],
    "evidence_summary": [
      {
        "evidence_id": "EVD-...",
        "verdict": "accepted | rejected | needs_more_work",
        "why": "Traceability, scope, direction, and dependency assessment"
      }
    ],
    "established_within_boundary": ["Claims established within their boundary"],
    "boundary_extension_candidates": [
      {
        "candidate": "Untested boundary described as a concrete DDM variable change",
        "expected_value": "high | medium | low",
        "feasibility": "feasible | uncertain | infeasible",
        "cost_profile": "low | medium | high | very_high",
        "disposition": "pending | accepted_for_mission | rejected_scientific | user_override",
        "reason": "Required when disposition is not pending"
      }
    ],
    "alternative_perspectives": ["A fundamentally different testable perspective"],
    "unresolved_alternatives": ["Unresolved competing explanations"],
    "open_questions": ["Open questions for the Director"],
    "capability_notes": ["Observed capability status"],
    "contribution_to_research": "Mechanism-level narrative",
    "recommended_next_direction": "Suggested direction; the Director decides"
  }
}
```

## 4. Trace events

Common trace fields: `schema`, `id` (`TRC-*`), `task_id`, `role`, `kind`,
`summary`, `content`, `created_at`.

Kinds: `task_start`, `brief_sent`, `attempt_start`, `attempt_end`, `tool_run`,
`delivery_received`, `status_change`, `task_end`, `checkpoint`.

Long-running subagents append milestones to `workspace/progress.jsonl`; the
engine imports them into `traces.jsonl` on delivery or explicit sync.

## 5. Roles and permissions

- **Director**: owns scientific direction, Mission proposals, Campaign
  continuation, and user interventions. It never drafts hypotheses, executes
  computational tools, or reviews evidence.
- **Engine**: deterministic single writer of logs, checkpoints, and views;
  validates structure, integrity, and role boundaries.
- **Scientific subagents**: Investigator, Challenger, Test Designer, Experiment
  Runner, Result Analyst, Evidence Reviewer, Mission Synthesizer. Each writes
  only `delivery.json` and `delivery.md` in its own workspace.
- **Direction Reviewer**: audits the Director's Mission proposals, next-direction
  choices, and terminal decisions before commitment. It does not draft science,
  execute tools, or decide the Campaign.

Independence is mandatory: a hypothesis author shall not review their own
evidence, and an Experiment Runner shall not review their own results. Only the
Experiment Runner may execute computational SKILLs.

## 6. Blackboard coordination

### 6.1 Single writer

Only the engine appends to `timeline.jsonl` and `traces.jsonl`, writes
checkpoints, and rebuilds views. Views are rebuilt after each event when
`views.auto_rebuild == after_each_event`.

### 6.2 Director directives

The Director writes `proposal.json`/`proposal.md` and `decision.json`/
`decision.md` under `blackboard/directives/round-<n>/`. A Direction Reviewer may
write `direction_review.json`/`direction_review.md` in the same round directory.
The engine validates, consumes, and appends the corresponding events.

### 6.3 Snapshot feedback

After each round, the engine rebuilds `research_snapshot.md` and the derived
views. The Director's next input is the snapshot plus the latest Mission report.

### 6.4 Experience library

Engineering knowledge is stored at `run_root/experience/experience.jsonl`. It is
not part of the logs and contains only environment, tool, script, workflow, and
pitfall lessons. Scientific conclusions are forbidden there.

## 7. State machines

- Campaign: `initializing -> active -> paused <-> active`; terminal states are
  `scientific_closure`, `non_convergent`, `operational_stop`, `failed`, and
  `cancelled`.
- Mission: `proposed -> admitted -> planning -> plan_frozen -> executing ->
  analyzing -> reviewing -> committed`; failure states are `blocked`,
  `rejected`, and `cancelled`.
- Hypothesis lifecycle: `proposed -> active <-> under_test -> dormant |
  superseded | retired`. Assessment is orthogonal: `unassessed -> supported |
  weakened | mixed | refuted`.
- Evidence: `candidate proposed -> reviewed -> accepted`; rejected and
  inconclusive records are preserved.

## 8. Scientific norms

- **Research universe**: a Mission may study only states, properties, and
  perturbations that the available computational SKILLs declare as supported
  (`U_DDM`). Unsupported physical variables are outside the research universe
  unless a capability contract explicitly supports them.
- **Computable mechanism first**: hypotheses are mechanism statements with a
  computable chain: design variable -> computable descriptors -> simulated
  property -> expected direction. Statistics operationalize the mechanism and
  never replace it.
- **DDM as a reliable virtual instrument**: outputs under one protocol are
  reproducible measurements of the simulated system. Fixed-seed variation is
  numerical residual; search randomness is exploration randomness.
- **Decision-graded evidence**: methods and conclusions are screening-grade,
  discrimination-grade, or confirmation-grade. Method grade shall match decision
  grade. Confirmation-grade methods are not default settings.
- **Space before precision**: early Missions cover multiple orthogonal
  DDM-supported design axes before precision is increased.
- **Contrast before correlation**: single-variable controlled contrasts decide
  between mechanisms; descriptor correlations only suggest mechanisms.
- **Decision value**: every computation and statistic shall be tied to a
  scientific decision it can change.
- **Law maturity**: a law candidate progresses through `lead`,
  `rule_candidate`, `rule`, and `law`. `law` requires mechanism separation,
  controlled discrimination, boundary mapping, decision utility, and
  reproducibility within `U_DDM`.
- **Scientific closure**: in strict mode, `scientific_closure` is permitted only
  for a law candidate at `law` maturity with all criteria `pass` or
  `not_applicable` and no pending high- or medium-priority research frontier.
  A shortlist alone is an `operational_stop`, not scientific closure.
- **Hypothesis narrowing**: claims move from qualitative to quantitative as data
  accumulate. No quantitative claim shall precede data; once data exist, claims
  shall not remain qualitative.
- **Freeze before execution**: target hypotheses, predictions, criteria, method,
  inputs, and decision rules are frozen before any tool run. New science is
  expressed as new hypothesis versions.
- **Evidence pipeline**: ToolRun -> RawResult -> Observation -> EvidenceCandidate
  -> Review -> Evidence. Tool success does not imply valid data; valid data do
  not imply evidence; accepted evidence does not imply a scientific conclusion.
- **Statistical inference**: the Result Analyst computes statistics with standard
  verified implementations only (`scipy.stats`, `statsmodels`). Hand-written
  bootstrap, partial-correlation, rank-transform, or FDR procedures are
  forbidden. The Experiment Runner produces raw data only.
- **Active falsification**: every mechanistic hypothesis is challenged before
  the test plan is frozen; alternatives and counterexamples are maintained.
- **Fidelity**: positive, negative, failed, conflicting, inconclusive, and
  minority records are preserved.
- **Applicability boundaries**: every claim declares its boundary; evidence
  outside the boundary cannot change the assessment.
- **Artifact integrity**: artifacts live under `artifacts/` and are referenced
  by relative path and sha256.

## 9. Budgets

- Outer budget: `campaign.max_outer_rounds` bounds outer-loop rounds;
  `director.propose_count` controls Missions per round.
- Inner budget: `mission.max_inner_rounds` bounds hypothesis-evidence rounds per
  Mission.
- `director.min_outer_rounds` is a lower bound only, never a sufficiency
  criterion.

## 10. Recovery

1. Read the latest checkpoint under `blackboard/checkpoints/CHK-*.json`.
2. Verify timeline and traces line counts and sha256.
3. Replay both logs to rebuild the model.
4. Re-run the renderer to rebuild derived views.

If the logs are newer than the checkpoint, the logs win and the checkpoint is
rebuilt; if the logs are shorter or hashes differ, stop and report.
