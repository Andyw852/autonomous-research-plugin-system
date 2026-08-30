---
name: rdkit
description: Cheminformatics toolkit for fine-grained molecular control. SMILES/SDF parsing, descriptors (MW, LogP, TPSA), fingerprints, substructure search, 2D/3D generation, similarity, reactions. For standard workflows with simpler interface, use datamol (wrapper around RDKit). Use rdkit for advanced control, custom sanitization, specialized algorithms.
license: BSD-3-Clause license
allowed-tools: Read Write Edit Bash
metadata:
  version: "1.2"
  skill-author: K-Dense Inc.
  compatibility: The locked environment uses CPython 3.12 and RDKit 2026.03.x from the PyPI package `rdkit`; `rdkit-pypi` is the legacy PyPI name.
---

# RDKit Cheminformatics Toolkit

## Overview

RDKit is a comprehensive cheminformatics library providing Python APIs for molecular analysis and manipulation. This skill provides guidance for reading/writing molecular structures, calculating descriptors, fingerprinting, substructure searching, chemical reactions, 2D/3D coordinate generation, and molecular visualization. Use this skill for drug discovery, computational chemistry, and cheminformatics research tasks.

**Current baseline (checked 2026-06-07):** RDKit **2026.03.3** is the latest GitHub/PyPI release (`rdkit` 2026.3.3 on PyPI). Official installation docs continue to recommend conda-forge for most users, while cross-platform PyPI wheels are published under the `rdkit` package name. `rdkit-pypi` is the old PyPI package name and should only appear when maintaining legacy environments.

## Capability Contract

This contract defines the supported research space for this SKILL. The Director,
Investigator, Challenger, and Test Designer shall treat it as the authoritative
boundary of what RDKit supports.

- **Can construct**: molecular objects from SMILES, MOL, SDF, InChI, and
  reaction products; 2D and 3D conformers with ETKDG embedding; molecular
  modifications such as substructure replacement and charge neutralization.
- **Can compute**: molecular descriptors, fingerprints, similarity,
  substructure matches, reaction transforms, pharmacophore features, and
  deterministic structure operations.
- **Can perturb**: molecular structure and substituents through editing APIs;
  conformational generation parameters and random seeds; reaction definitions.
- **Cannot do**: quantum mechanical energies, force-field simulation beyond the
  bundled MMFF optimization, protein-ligand scoring, synthesis feasibility, or
  experimental properties.
- **Protocol identity**: record RDKit version, environment interpreter,
  descriptor/fingerprint parameter choices, chirality and aromaticity settings,
  and random seeds for conformer generation.
- **Randomness**: ETKDG embedding uses a seed; fixed-seed reruns are
  reproducibility checks, not independent physical replicates.
- **Cost ladder**: descriptor and fingerprint calculation is low cost; large
  libraries and 3D conformer generation are medium cost.



## Installation and Setup

From this SKILL directory, create and synchronize its private CPython 3.12
environment from the committed lock file:

```bash
bash scripts/setup_env.sh
```

The script creates `.venv` only inside this SKILL and applies `requirements.lock`
with `uv pip sync --strict`. Do not install RDKit into the project interpreter,
the PyTDC environment, or a mixed conda/pip environment. Run bundled commands with
the locked interpreter:

```bash
.venv/bin/python scripts/molecular_properties.py --help
```

The standalone RDKit SKILL intentionally uses the current PyPI `rdkit` package.
PyTDC pins an older RDKit in its own private environment; keeping the environments
separate prevents that legitimate version difference from becoming a conflict.

## Core Capabilities

Twelve capability areas, each with worked code, are documented in
[references/core_capabilities.md](references/core_capabilities.md):

| # | Area | Covers |
| --- | --- | --- |
| 1 | Molecular I/O and creation | SMILES, MOL files and blocks, InChI, SDF and SMILES suppliers, multithreaded reading, writers |
| 2 | Sanitization and validation | disabling automatic sanitization, manual and partial sanitization, detecting problems first |
| 3 | Analysis and properties | atom and bond iteration, ring information and SSSR, chirality and stereochemistry, fragments |
| 4 | Descriptors | MW, LogP, TPSA, H-bond donors/acceptors, rotatable bonds, aromatic rings, bulk calculation, drug-likeness |
| 5 | Fingerprints and similarity | topological, Morgan/ECFP via `rdFingerprintGenerator`, MACCS, atom pair, torsion, Avalon; Tanimoto and other metrics; Butina clustering |
| 6 | Substructure searching | SMARTS queries, match retrieval, and a library of common patterns |
| 7 | Chemical reactions | reaction SMARTS, applying reactions, reaction fingerprints |
| 8 | 2D and 3D coordinates | depiction, template alignment, ETKDG embedding, force-field optimization, RMSD, constrained embedding |
| 9 | Visualization | single and grid images, substructure highlighting, custom drawer options, Jupyter integration, fingerprint bit environments |
| 10 | Molecular modification | explicit hydrogens, Kekulization, aromaticity, substructure replacement, charge neutralization |
| 11 | Hashes and standardization | Murcko scaffold and canonical hashes, regioisomer hashes, randomized SMILES for augmentation |
| 12 | Pharmacophore and 3D features | feature factories and feature extraction |

Worked workflows and the performance, thread-safety, and version-sensitivity notes are in
[references/workflows_and_best_practices.md](references/workflows_and_best_practices.md).

Prefer portable exchange formats (SMILES, SDF) for shared data; for local caches RDKit's
binary molecule representation avoids generic pickle.

## Common Pitfalls

1. **Forgetting to check for None:** Always validate molecules after parsing
2. **Sanitization failures:** Use `DetectChemistryProblems()` to debug
3. **Missing hydrogens:** Use `AddHs()` when calculating properties that depend on hydrogen
4. **2D vs 3D:** Generate appropriate coordinates before visualization or 3D analysis
5. **SMARTS matching rules:** Remember that unspecified properties match anything
6. **Thread safety with MolSuppliers:** Don't share supplier objects across threads

## Resources

### references/

This skill includes detailed API reference documentation:

- `api_reference.md` - Comprehensive listing of RDKit modules, functions, and classes organized by functionality
- `descriptors_reference.md` - Complete list of available molecular descriptors with descriptions
- `smarts_patterns.md` - Common SMARTS patterns for functional groups and structural features

Load these references when needing specific API details, parameter information, or pattern examples.

Only the files listed in `references/` and `scripts/` are bundled local resources. Names such as `rdkit`, `datamol`, `scipy`, and `sklearn` refer to installable Python packages, not local files in this skill.

### scripts/

Example scripts for common RDKit workflows:

- `setup_env.sh` - Create/synchronize the private locked `.venv`
- `molecular_properties.py` - Calculate comprehensive molecular properties and descriptors
- `similarity_search.py` - Perform fingerprint-based similarity screening
- `substructure_filter.py` - Filter molecules by substructure patterns

These scripts can be executed directly or used as templates for custom workflows.
