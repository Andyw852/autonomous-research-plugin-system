# Minimal End-to-End cofkit Workflow

This example runs a small but complete cofkit pipeline:

1. Build one imine COF (TAPB + TFB, hcb topology)
2. Run Zeo++ pore analysis
3. Run LAMMPS optimization with EQeq charge assignment
4. Run gRASPA H2 adsorption isotherm (EQeq charge assignment again)

The simulation parameters are intentionally tiny so the whole pipeline can be
smoke-tested quickly. **The resulting adsorption numbers are not production
values.**

## Quick start

From the cofkit skill root:

```bash
cd skills/cofkit
.venv/bin/python examples/minimum/run_minimal_end_to_end.py
```

The script uses these machine-specific defaults; override with environment
variables if your paths differ:

```bash
export COFKIT_LMP_PATH=/path/to/lmp
export COFKIT_ZEOPP_PATH=/path/to/network
export COFKIT_EQEQ_PATH=/path/to/eqeq
export COFKIT_GRASPA_PATH=/path/to/nvc_main.x
export EQEQ_DATA_DIR=/path/to/EQeq/data
```

## Manual step-by-step commands

### 1. Build a COF

```bash
.venv/bin/cofkit build single-pair \
  --template-id imine_bridge \
  --first-smiles 'C1=CC(=CC=C1C2=CC(=CC(=C2)C3=CC=C(C=C3)N)C4=CC=C(C=C4)N)N' \
  --second-smiles 'C1=C(C=C(C=C1C=O)C=O)C=O' \
  --first-id tapb \
  --second-id tfb \
  --topology hcb \
  --no-all-topologies \
  --output-dir build_output
```

### 2. Sanitize the CIF for EQeq

The local EQeq build crashes on atom labels containing underscores (cofkit writes
`m1_C1`, `m2_C1`). Create a copy with underscores removed from the label column:

```bash
python3 - <<'PY'
from pathlib import Path
src = Path("build_output/cifs/valid/tapb__tfb__hcb.cif").read_text()
out = src.replace("m1_", "m1").replace("m2_", "m2")
Path("tapb__tfb__hcb_sanitized.cif").write_text(out)
PY
```

### 3. Zeo++

```bash
.venv/bin/cofkit analyze zeopp \
  build_output/cifs/valid/tapb__tfb__hcb.cif \
  --output-dir zeopp_output \
  --json
```

### 4. LAMMPS optimization + EQeq charges

EQeq looks for `ionizationdata.dat` and `chargecenters.dat` in its working
directory. Pre-create the eqeq directory and copy the data files before running:

```bash
mkdir -p lammps_output/eqeq
cp /path/to/EQeq/data/ionizationdata.dat lammps_output/eqeq/
cp /path/to/EQeq/data/chargecenters.dat   lammps_output/eqeq/

.venv/bin/cofkit calculate lammps-optimize \
  tapb__tfb__hcb_sanitized.cif \
  --output-dir lammps_output \
  --forcefield dreiding \
  --charge-model eqeq \
  --pre-minimization-steps 0 \
  --max-iterations 20 \
  --max-evaluations 200 \
  --timeout-seconds 120 \
  --eqeq-timeout-seconds 120 \
  --json
```

### 5. gRASPA H2 isotherm

Again pre-create the EQeq data directory:

```bash
mkdir -p graspa_output/eqeq
cp /path/to/EQeq/data/ionizationdata.dat graspa_output/eqeq/
cp /path/to/EQeq/data/chargecenters.dat   graspa_output/eqeq/

.venv/bin/cofkit calculate graspa-isotherm \
  lammps_output/tapb__tfb__hcb_sanitized_lammps_optimized.cif \
  --output-dir graspa_output \
  --component H2_DREIDING \
  --pressure 500000 \
  --pressure 1000000 \
  --temperature 77 \
  --forcefield dreiding \
  --initialization-cycles 10 \
  --equilibration-cycles 10 \
  --production-cycles 20 \
  --eqeq-timeout-seconds 120 \
  --graspa-timeout-seconds 120 \
  --json
```

## Expected outputs

```text
build_output/cifs/valid/tapb__tfb__hcb.cif
tapb__tfb__hcb_sanitized.cif
zeopp_output/zeopp_report.json
lammps_output/lammps_report.json
lammps_output/tapb__tfb__hcb_sanitized_lammps_optimized.cif
lammps_output/eqeq/*.cif_EQeq_ewald_1.20_-2.00.*
graspa_output/graspa_isotherm_report.json
graspa_output/isotherm/results.csv
graspa_output/eqeq/*.cif_EQeq_ewald_1.20_-2.00.*
```

## Precautions / known issues

1. **EQeq cannot parse cofkit atom labels with underscores.**
   - Symptom: `terminate called after throwing an instance of 'std::out_of_range'`
     or `basic_string::substr ... npos`.
   - Workaround: sanitize the CIF label column before any EQeq-using workflow.
   - The bundled `run_minimal_end_to_end.py` does this automatically.

2. **EQeq data files must be in the EQeq run directory.**
   - cofkit invokes EQeq with `cwd=<output>/eqeq` and does not pass explicit
     `ionizationdata.dat` / `chargecenters.dat` paths.
   - Pre-create `<output>/eqeq` and copy both files there before running
     LAMMPS or gRASPA workflows.

3. **gRASPA Widom may fail with CUDA device errors.**
   - `graspa-widom` defaults to `UseGPUReduction yes`.
   - If the process cannot see a GPU, use `CUDA_VISIBLE_DEVICES=0` or set
     `GraspaWidomSettings(use_gpu_reduction=False)` in Python.
   - `graspa-isotherm` / `graspa-mixture` default to CPU reduction and are less
     likely to hit this issue.
   - See `docs/troubleshooting.md` for details.

4. **Tiny cycles produce zero / non-finite adsorption numbers.**
   - This example uses `10/10/20` cycles only for a fast smoke test.
   - For real H2 storage screening, use production-quality settings and verify
     convergence (e.g., hundreds of thousands of production cycles).

5. **LAMMPS may emit warnings.**
   - EQeq label mismatch warnings are expected after sanitization; cofkit maps
     charges by atom order. Verify atom ordering before trusting charges.
   - Periodic spanning-tree warnings are geometry/typing diagnostics; inspect the
     LAMMPS report before using optimized structures in downstream simulations.

6. **Always set explicit external-tool paths or `COFKIT_*` env vars.**
   - See `docs/external-tools-environment.md` for this machine's current paths.
