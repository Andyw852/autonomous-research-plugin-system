# cofkit Troubleshooting

Common runtime issues and their fixes when using cofkit with external tools.

## gRASPA: CUDA Error — no CUDA-capable device is detected

### Symptom

Running gRASPA (often through `cofkit calculate graspa-widom`) fails with:

```text
CUDA Error: Error allocating Malloc: no CUDA-capable device is detected.
```

The machine may still have GPUs visible to `nvidia-smi`:

```text
GPU 0: NVIDIA A800 80GB PCIe
GPU 1: NVIDIA A800 80GB PCIe
```

### Root cause

This means the **gRASPA process cannot see a CUDA device at runtime**, not that the
machine lacks a GPU. Common causes:

- `CUDA_VISIBLE_DEVICES` is set to an empty string or an invalid value.
- The process runs inside a container / sandbox / subagent environment without GPU
  passthrough or without `/dev/nvidia*` devices.
- The process was started through `sudo`, a scheduler, or a background wrapper that
  did not inherit the GPU environment.

### Why cofkit triggers this

cofkit's `graspa-widom` defaults to GPU reduction:

```python
GraspaWidomSettings(use_gpu_reduction=True)
```

This writes:

```text
UseGPUReduction yes
```

into the generated `simulation.input`, so Widom runs try to allocate GPU memory.
`graspa-isotherm` and `graspa-mixture` default to `use_gpu_reduction=False`, so they
usually do not trigger this error.

### Reproduce / verify

```bash
# This should reproduce the error when no GPU is visible to the process
CUDA_VISIBLE_DEVICES='' \
/home/taoshijie/bin/gRASPA/src_clean/nvc_main.x
```

```bash
# This should work when a GPU is visible
CUDA_VISIBLE_DEVICES=0 \
/home/taoshijie/bin/gRASPA/src_clean/nvc_main.x
```

### Solutions

1. **Expose a GPU to the running process (recommended for GPU runs)**

```bash
export CUDA_VISIBLE_DEVICES=0
# or
export CUDA_VISIBLE_DEVICES=1
```

Verify before running:

```bash
echo "$CUDA_VISIBLE_DEVICES"
nvidia-smi
```

2. **Ensure subagent / container environments inherit the GPU**

When running through autonomous-research-plugin-system, the Experiment Runner
subagent must run in an environment that can see the GPU:

- plain shell: set `CUDA_VISIBLE_DEVICES=0`
- Docker / container: add `--gpus all` or `--gpus '"device=0"'`
- background jobs: make sure the job inherits the GPU device and environment
- check `/dev/nvidia*` exists and is accessible

3. **Disable GPU reduction for Widom (CPU fallback)**

If the machine GPU is unavailable or CPU-only execution is acceptable, use the
cofkit Python API:

```python
from cofkit.graspa import GraspaWidomSettings, run_graspa_widom_workflow

settings = GraspaWidomSettings(
    use_gpu_reduction=False,
    temperature=77.0,
    pressure=100000.0,
)

run_graspa_widom_workflow(
    "structure.cif",
    output_dir="out/widom",
    widom_settings=settings,
)
```

The generated `simulation.input` will then contain:

```text
UseGPUReduction no
```

and gRASPA will run the Widom calculation on CPU.

### Notes

- `graspa-isotherm` and `graspa-mixture` already default to CPU reduction
  (`use_gpu_reduction=False`), so they are less likely to hit this error.
- If you need GPU acceleration, ensure the gRASPA binary is the CUDA/OpenACC build
  and that the NVIDIA HPC SDK / CUDA runtime libraries are visible to the process.

## EQeq: CIF atom labels with underscores crash

### Symptom

`cofkit calculate lammps-optimize` or any gRASPA workflow that runs EQeq fails
with:

```text
terminate called after throwing an instance of 'std::out_of_range'
  what():  basic_string::substr: __pos (which is 18446744073709551615) > this->size()
```

This happens because cofkit-generated CIF atom labels look like `m1_C1` / `m2_C1`,
and the local EQeq build cannot parse atom labels containing underscores.

### Fix

Sanitize the CIF before any EQeq-using workflow. Replace `m1_` → `m1` and
`m2_` → `m2` throughout the whole CIF (atom rows and bond-loop references):

```bash
python3 - <<'PY'
from pathlib import Path
src = Path("build_output/cifs/valid/tapb__tfb__hcb.cif").read_text()
out = src.replace("m1_", "m1").replace("m2_", "m2")
Path("tapb__tfb__hcb_sanitized.cif").write_text(out)
PY
```

Then run `lammps-optimize` / `graspa-*` on the sanitized CIF.

## EQeq: missing ionizationdata.dat / chargecenters.dat

cofkit runs EQeq with its working directory set to `<output>/eqeq`, but does not
pass explicit data-file paths. The local EQeq build looks for:

- `ionizationdata.dat`
- `chargecenters.dat`

in that working directory.

### Fix

Before running an EQeq-using cofkit workflow, pre-create the eqeq output
directory and copy both data files into it:

```bash
mkdir -p lammps_output/eqeq
cp /path/to/EQeq/data/ionizationdata.dat lammps_output/eqeq/
cp /path/to/EQeq/data/chargecenters.dat   lammps_output/eqeq/
```

The bundled `examples/minimum/run_minimal_end_to_end.py` does this automatically.
