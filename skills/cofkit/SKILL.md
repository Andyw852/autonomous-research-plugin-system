---
name: cofkit
description: Reaction-aware periodic assembly toolkit for covalent organic frameworks (COFs). Provides monomer detection, binary-bridge and ring-forming reaction templates, topology-aware assembly, CIF export, coarse validation, decomposition, and optional Zeo++/LAMMPS/EQeq/gRASPA/RASPA2 wrappers.
license: MIT
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.0"
  skill-author: csllpr (cofkit upstream)
  compatibility: Python >=3.10; dependencies include gemmi, openbabel, pandas, pymatgen, rdkit. Optional external tools: Zeo++, LAMMPS, EQeq, gRASPA/RASPA2. Verified commit 082c1a5 (2026-08-19).
---

# cofkit (COF Assembly Toolkit)

## Overview

`cofkit` is a computational chemistry toolkit for building, analyzing, validating,
and simulating covalent organic frameworks (COFs). It is intended for use by the
Experiment Runner when a research plan requires COF construction from SMILES or
monomer libraries, CIF generation, COFid decomposition/validation, or optional
pore/adsorption/optimization workflows.

## DDM Capability Contract

This contract defines the DDM-supported research space for this SKILL. The
Director, Investigator, Challenger, and Test Designer shall treat it as the
authoritative boundary of what cofkit can support.

- **Can construct**: periodic COF/CTF frameworks from monomer SMILES through
  cofkit reaction templates, including imine binary-bridge and ring-forming
  (triazine/boroxine) routes; topology and stacking-mode selection; batch
  monomer libraries. Supported outputs include CIF files and build summaries.
- **Can compute**: structural descriptors and validation via Zeo++ (pore limiting
  diameter, accessible surface area, void fraction), LAMMPS geometry
  optimization, EQeq partial charges, gRASPA Widom insertion, single- or
  multi-component adsorption isotherms and mixture selectivities, and hybrid
  MD/MC workflows.
- **Can perturb**: monomer composition and linker chemistry, reaction template,
  topology, stacking mode, force-field parameters, charge assignment (including
  charge-off controls), and simulation conditions such as temperature, pressure,
  cycles, and seed, where the corresponding wrappers accept those settings.
- **Cannot do**: real synthesis kinetics, nucleation or growth, solvent or
  processing history, amorphous or disordered structure evolution, and physical
  transport or aging processes that the bundled tools do not model.
- **Protocol identity**: record the cofkit commit/version, template identifiers,
  force field, charge method, external tool paths and versions, random seed,
  cycle counts, and convergence settings for every comparative run. All
  comparisons in one Mission shall share one protocol identity unless a protocol
  change is an explicitly planned sensitivity control.
- **Randomness**: cofkit build and Zeo++ analysis are deterministic for fixed
  inputs. gRASPA Monte Carlo workflows use a seed; fixed-seed reruns are
  numerical reproducibility checks, not independent physical replicates. Use one
  fixed seed for screening-grade exploration and reserve multi-seed production for
  confirmation-grade validation.
- **Cost ladder**: structural build and descriptor analysis are low cost; LAMMPS
  optimization and exploratory GCMC are medium cost; production multi-seed
  isotherms and mixtures are high cost. Each level shall be tied to a decision it
  changes.
- **Machine availability**: confirm external tool availability with
  `docs/external-tools-environment.md` before planning LAMMPS, EQeq, gRASPA, or
  Zeo++ steps.



This directory is the upstream `csllpr/cofkit` repository cloned as a plugin
computational skill. The upstream repository already contains rich documentation;
use this SKILL.md as the entry point and then open the referenced files for exact
APIs and command details.

## Repository layout

- `README.md` — quick start, first builds, CLI groups
- `docs/` — getting-started, building, analysis-validation, calculations, Python API, external tools
- `tutorials/` — cross-platform Jupyter tutorials
- `examples/` — runnable example scripts and monomer libraries
  - `examples/minimum/` — minimal end-to-end workflow: COF build → Zeo++ → LAMMPS+EQeq → gRASPA H2 isotherm
- `src/cofkit/` — Python package source
- `tests/` — upstream test suite

## Installation

From this SKILL directory (`skills/cofkit/`), use `uv` to create/verify the
project environment:

```bash
uv sync --locked
uv run cofkit --help
```

For the upstream test suite:

```bash
uv sync --locked --extra dev
uv run pytest -q
```

Alternative conda path (see `environment.yml`):

```bash
conda env create --file environment.yml
conda activate cofkit
python -m pip install --no-deps .
cofkit --help
```

Do not install `cofkit` into the project interpreter or another SKILL's private
environment. Keep this skill's environment separate from `pytdc` and `rdkit`
unless a plan explicitly requires sharing dependencies.

## Common workflows

### Build a single imine COF from SMILES

```bash
uv run cofkit build single-pair \
  --template-id imine_bridge \
  --first-smiles '<monomer SMILES>' \
  --second-smiles '<monomer SMILES>' \
  --first-id tapb \
  --second-id tfb \
  --output-dir out/cli_single_pair
```

### Build a triazine-linked CTF

```bash
uv run cofkit build ring-forming \
  --template-id triazine_trimerization \
  --smiles 'N#Cc1ccc(C#N)cc1' \
  --topology hcb \
  --stacking AA \
  --output-dir out/ctf1
```

### Discover available templates

```bash
uv run cofkit build list-templates
```

### Other main CLI groups

```bash
uv run cofkit build --help
uv run cofkit analyze --help
uv run cofkit calculate --help
uv run cofkit validate --help
```

Common commands:

- `cofkit build batch-binary-bridge`
- `cofkit build batch-all-binary-bridges`
- `cofkit build default-library`
- `cofkit analyze classify-output`
- `cofkit analyze decompose`
- `cofkit analyze zeopp`
- `cofkit calculate lammps-optimize`
- `cofkit calculate graspa-widom`
- `cofkit calculate graspa-isotherm`
- `cofkit calculate graspa-mixture`
- `cofkit calculate hybrid-mdmc`
- `cofkit validate simple`
- `cofkit validate optimize`

## Minimal end-to-end example

A validated smoke-test pipeline is provided in `examples/minimum/`. It covers:

1. COF construction (`build single-pair`, imine hcb)
2. Zeo++ pore analysis
3. LAMMPS optimization with EQeq charge assignment
4. gRASPA H2 adsorption isotherm

Run it with:

```bash
cd skills/cofkit
.venv/bin/python examples/minimum/run_minimal_end_to_end.py
```

Read `examples/minimum/README.md` before dispatching an Experiment Runner. It
documents machine-specific EQeq data-file setup, the EQeq underscore-label bug
and workaround, GPU/CUDA caveats, and why tiny cycles are smoke-test-only.

## Workflow routing

For exact request-to-command mapping, output artifact names, output-reading rules,
and common traps, read **`docs/intent-routing.md`** first. Quick surface:

- **Build chemistry**: `build list-templates`, `build single-pair`, `build batch-binary-bridge`, `build batch-all-binary-bridges`, `build default-library`
- **Analyze**: `analyze classify-output`, `analyze decompose`, `analyze zeopp`
- **Calculate**: `calculate lammps-optimize`, `calculate graspa-widom`, `calculate graspa-isotherm`, `calculate graspa-mixture`, `calculate hybrid-mdmc`
- **Validate**: `validate simple`, `validate optimize`
- **Python API**: `COFEngine` for project-style generation, `BatchStructureGenerator` for batch/library workflows

Always read the generated artifacts before reporting success:

- `summary.json` / `manifest.jsonl` / `summary.md` / `combined_summary.json` for builds
- `classification_manifest.jsonl` for output triage
- `zeopp_report.json`, `lammps_report.json`, `graspa_*_report.json`, `hybrid_mdmc_report.json` for calculation workflows

## Optional external tools

The Python package works without external simulation binaries for build and basic
validation. The wrapper commands need explicit paths via environment variables or
`--*-path` flags:

- `COFKIT_ZEOPP_PATH` — Zeo++ `network` binary for `analyze zeopp`
- `COFKIT_LMP_PATH` — LAMMPS executable for LAMMPS optimization / MD / validate optimize
- `COFKIT_EQEQ_PATH` — EQeq executable for charge staging
- `COFKIT_GRASPA_PATH` — gRASPA executable for Monte Carlo workflows
- `COFKIT_RASPA2_PATH` — RASPA2 executable for CPU Monte Carlo workflows

Before running external-tool workflows, check `docs/external-tools.md` and
`docs/external-tools-environment.md` for machine-specific availability and
paths. These tools may be expensive and require user approval if they consume
significant compute or external resources.

## Plugin integration rules

- Only the **Experiment Runner** subagent may use this computational skill.
- Attach the relevant `cofkit` docs and scripts when dispatching the Experiment
  Runner.
- Record the exact command, input SMILES/CIF paths, output directories, environment
  pins, and external-tool paths in the delivery so the run is reproducible.
- Do not let the main agent or engine execute `cofkit` directly; the engine only
  schedules, validates, and records.

## Further reading

- `docs/getting-started.md` — install and verification
- `docs/building.md` — single-pair, batch, topology, stacking
- `docs/analysis-validation.md` — classify, decompose, validate, Zeo++
- `docs/calculations.md` — LAMMPS, EQeq, gRASPA/RASPA2, hybrid MD/MC
- `docs/external-tools-environment.md` — current machine tool availability and paths
- `docs/intent-routing.md` — request-to-command routing, output reading, common traps
- `docs/troubleshooting.md` — common runtime errors (e.g. gRASPA CUDA device) and fixes
- `docs/python-api.md` — `COFEngine` and `BatchStructureGenerator`
- `docs/CURRENT_SCOPE.md` — implemented capabilities and known limits
