# External Tools Environment (Machine Status)

This file records which external computation tools `cofkit` can use and whether
they are currently available on this machine. Read this before dispatching an
Experiment Runner task that needs LAMMPS, gRASPA/RASPA2, Zeo++, or EQeq.

## Tool roles

| Tool | Role in cofkit |
| --- | --- |
| LAMMPS | Structure optimization and molecular dynamics on explicit-bond COF CIFs |
| gRASPA | Adsorption Monte Carlo backend (Widom, isotherm, mixture, hybrid MD/MC) |
| RASPA2 | Alternative CPU Monte Carlo backend; same adsorption workflows via `--backend raspa2` |
| Zeo++ | Pore analysis: accessible surface area, pore volume, channel analysis |
| EQeq | Charge assignment / electrostatic pre-step for LAMMPS and gRASPA/RASPA2 workflows |

RASPA2 is not required if gRASPA is installed and the plan uses the default
backend. RASPA2 is only needed when explicitly selecting `--backend raspa2`.

## Current machine detection

Checked on this machine:

| Tool | Status | Executable path |
| --- | --- | --- |
| LAMMPS | available | `/home/taoshijie/miniconda3/envs/lammps/bin/lmp` |
| LAMMPS (MPI) | available | `/home/taoshijie/miniconda3/envs/lammps/bin/lmp_mpi` |
| gRASPA | available | `/home/taoshijie/bin/gRASPA/src_clean/nvc_main.x` |
| RASPA2 | **not installed** | no `simulate` executable found |
| Zeo++ | available | `/home/taoshijie/bin/zeoplusplus/network` |
| EQeq | available | `/home/taoshijie/bin/EQeq/eqeq` |

No `COFKIT_*` environment variables were set in the shell at check time.

## Recommended environment variables

Set these in the shell/environment before running cofkit external-tool commands:

```bash
export COFKIT_LMP_PATH=/home/taoshijie/miniconda3/envs/lammps/bin/lmp
export COFKIT_GRASPA_PATH=/home/taoshijie/bin/gRASPA/src_clean/nvc_main.x
export COFKIT_ZEOPP_PATH=/home/taoshijie/bin/zeoplusplus/network
export COFKIT_EQEQ_PATH=/home/taoshijie/bin/EQeq/eqeq
```

If RASPA2 is installed later, its executable is normally named `simulate` and
should be configured with:

```bash
export COFKIT_RASPA2_PATH=/path/to/RASPA2/bin/simulate
```

Equivalent CLI flags can be used instead of environment variables:

- `--lmp-path`
- `--graspa-path`
- `--raspa2-path`
- `--zeopp-path`
- `--eqeq-path`

## Related commands

- LAMMPS optimization: `cofkit calculate lammps-optimize`
- LAMMPS validation: `cofkit validate optimize`
- Zeo++ pore analysis: `cofkit analyze zeopp`
- gRASPA/RASPA2 Widom: `cofkit calculate graspa-widom`
- gRASPA/RASPA2 isotherm: `cofkit calculate graspa-isotherm`
- gRASPA/RASPA2 mixture: `cofkit calculate graspa-mixture`
- Hybrid MD/MC: `cofkit calculate hybrid-mdmc`

## How to verify a binary

```bash
# LAMMPS
/home/taoshijie/miniconda3/envs/lammps/bin/lmp -h

# Zeo++
/home/taoshijie/bin/zeoplusplus/network -help

# gRASPA
/home/taoshijie/bin/gRASPA/src_clean/nvc_main.x -h

# EQeq
/home/taoshijie/bin/EQeq/eqeq
```

RASPA2 can be verified by running `simulate -h` once it is installed.
