#!/usr/bin/env python3
"""Minimal end-to-end cofkit workflow.

Covers:
  1. COF construction (single-pair imine hcb)
  2. Zeo++ pore analysis
  3. LAMMPS optimization (with EQeq charge assignment)
  4. EQeq charge calculation (inside LAMMPS and gRASPA workflows)
  5. gRASPA H2 adsorption isotherm

Run from the plugin skill root or from this directory with the cofkit venv:

    cd skills/cofkit
    .venv/bin/python examples/minimum/run_minimal_end_to_end.py

The script uses intentionally tiny simulation cycles so the full pipeline can be
smoke-tested quickly. The resulting adsorption numbers are NOT production values.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COFKIT_BIN = ROOT / ".venv" / "bin" / "cofkit"

DEFAULT_LMP = "/home/taoshijie/miniconda3/envs/lammps/bin/lmp"
DEFAULT_ZEOPP = "/home/taoshijie/bin/zeoplusplus/network"
DEFAULT_EQEQ = "/home/taoshijie/bin/EQeq/eqeq"
DEFAULT_EQEQ_DATA = "/home/taoshijie/bin/EQeq/data"
DEFAULT_GRASPA = "/home/taoshijie/bin/gRASPA/src_clean/nvc_main.x"

HERE = Path(__file__).resolve().parent


def ensure_env() -> None:
    os.environ.setdefault("COFKIT_LMP_PATH", DEFAULT_LMP)
    os.environ.setdefault("COFKIT_ZEOPP_PATH", DEFAULT_ZEOPP)
    os.environ.setdefault("COFKIT_EQEQ_PATH", DEFAULT_EQEQ)
    os.environ.setdefault("COFKIT_GRASPA_PATH", DEFAULT_GRASPA)


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600) -> None:
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, cwd=cwd, check=True, timeout=timeout)


def sanitize_cif_for_eqeq(src: Path, dst: Path) -> None:
    """EQeq crashes on atom labels containing underscores.

    cofkit CIF labels look like m1_C1 / m2_C1. Remove underscores everywhere in
    the CIF so atom-site rows and bond-loop references stay consistent.
    """
    text = src.read_text(encoding="utf-8")
    text = text.replace("m1_", "m1").replace("m2_", "m2")
    dst.write_text(text, encoding="utf-8")


def prepare_eqeq_data(output_root: Path) -> None:
    """Place EQeq data files in the eqeq run directory before cofkit runs.

    The local EQeq binary looks for ionizationdata.dat / chargecenters.dat in
    its current working directory, and cofkit does not pass explicit data paths.
    """
    eqeq_dir = output_root / "eqeq"
    eqeq_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(os.environ.get("EQEQ_DATA_DIR", DEFAULT_EQEQ_DATA))
    shutil.copy2(data_dir / "ionizationdata.dat", eqeq_dir / "ionizationdata.dat")
    shutil.copy2(data_dir / "chargecenters.dat", eqeq_dir / "chargecenters.dat")


def main() -> None:
    ensure_env()
    work = HERE
    work.mkdir(parents=True, exist_ok=True)

    # 1. Build a single imine COF (TAPB + TFB, hcb topology)
    build_dir = work / "build_output"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    run([
        str(COFKIT_BIN), "build", "single-pair",
        "--template-id", "imine_bridge",
        "--first-smiles",
        "C1=CC(=CC=C1C2=CC(=CC(=C2)C3=CC=C(C=C3)N)C4=CC=C(C=C4)N)N",
        "--second-smiles", "C1=C(C=C(C=C1C=O)C=O)C=O",
        "--first-id", "tapb", "--second-id", "tfb",
        "--topology", "hcb", "--no-all-topologies",
        "--output-dir", str(build_dir),
    ], timeout=300)
    built_cif = build_dir / "cifs" / "valid" / "tapb__tfb__hcb.cif"
    if not built_cif.is_file():
        raise SystemExit(f"build did not produce expected CIF: {built_cif}")

    # 2. EQeq-compatible CIF (no underscores in atom labels)
    sanitized_cif = work / "tapb__tfb__hcb_sanitized.cif"
    sanitize_cif_for_eqeq(built_cif, sanitized_cif)

    # 3. Zeo++ pore analysis
    zeopp_dir = work / "zeopp_output"
    if zeopp_dir.exists():
        shutil.rmtree(zeopp_dir)
    run([
        str(COFKIT_BIN), "analyze", "zeopp",
        str(built_cif), "--output-dir", str(zeopp_dir), "--json",
    ], timeout=300)

    # 4. LAMMPS optimization + EQeq charge assignment
    lammps_dir = work / "lammps_output"
    if lammps_dir.exists():
        shutil.rmtree(lammps_dir)
    prepare_eqeq_data(lammps_dir)
    run([
        str(COFKIT_BIN), "calculate", "lammps-optimize",
        str(sanitized_cif),
        "--output-dir", str(lammps_dir),
        "--forcefield", "dreiding",
        "--charge-model", "eqeq",
        "--pre-minimization-steps", "0",
        "--max-iterations", "20",
        "--max-evaluations", "200",
        "--timeout-seconds", "120",
        "--eqeq-timeout-seconds", "120",
        "--json",
    ], timeout=600)
    optimized_candidates = sorted(lammps_dir.glob("*_lammps_optimized.cif"))
    if not optimized_candidates:
        raise SystemExit(f"LAMMPS did not produce optimized CIF under {lammps_dir}")
    optimized_cif = optimized_candidates[0]

    # 5. gRASPA H2 isotherm (EQeq runs internally again)
    graspa_dir = work / "graspa_output"
    if graspa_dir.exists():
        shutil.rmtree(graspa_dir)
    prepare_eqeq_data(graspa_dir)
    run([
        str(COFKIT_BIN), "calculate", "graspa-isotherm",
        str(optimized_cif),
        "--output-dir", str(graspa_dir),
        "--component", "H2_DREIDING",
        "--pressure", "500000",
        "--pressure", "1000000",
        "--temperature", "77",
        "--forcefield", "dreiding",
        "--initialization-cycles", "10",
        "--equilibration-cycles", "10",
        "--production-cycles", "20",
        "--eqeq-timeout-seconds", "120",
        "--graspa-timeout-seconds", "120",
        "--json",
    ], timeout=600)

    print("\nMinimal end-to-end workflow completed.")
    print(f"  COF CIF:      {built_cif}")
    print(f"  Sanitized CIF:{sanitized_cif}")
    print(f"  Zeo++ report: {zeopp_dir / 'zeopp_report.json'}")
    print(f"  LAMMPS report:{lammps_dir / 'lammps_report.json'}")
    print(f"  Optimized CIF:{optimized_cif}")
    print(f"  gRASPA report:{graspa_dir / 'graspa_isotherm_report.json'}")


if __name__ == "__main__":
    main()
