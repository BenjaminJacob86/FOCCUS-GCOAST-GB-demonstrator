#!/usr/bin/env python3
"""
Compute difference indicator NetCDF and PMTiles between two scenario runs.

Takes indicator_nc/ folders from two SCHISM runs (e.g. no_veg and with_veg)
and produces diff = with_veg − no_veg for each matching indicator variable.

The diff NetCDF files have the same structure as the originals (SCHISM node
mesh + one static variable), so schism_vector_tiles_triangles.py can tile
them identically.

Usage (HPC):

  python compute_scenario_diff.py \
    --noveg-nc-dir  /gpfs/.../gb_wave_routine/indicator_nc \
    --veg-nc-dir    /gpfs/.../gb_wave_routine_seagrass/indicator_nc \
    --output-nc-dir ./diff/indicator_nc \
    --output-pmtiles-dir ./diff/indicator_pmtiles

  # NetCDF only (tile later):
  python compute_scenario_diff.py ... --skip-pmtiles

  # One indicator:
  python compute_scenario_diff.py ... --only ssh

Sign convention: diff = with_veg − no_veg
  Negative → indicator lower with vegetation (e.g. wave attenuation)
  Positive → higher with vegetation
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TILES_SCRIPT = SCRIPT_DIR / "schism_vector_tiles_triangles.py"

SCHISM_UTILS_DEFAULT = "/gpfs/work/ksddata/code/schism/scripts/schism-hereon-utilities/"

# Must match Erosion_risk_vector_tiles_for_streamlit.py
INDICATOR_EXPORTS: dict[str, tuple[str, str]] = {
    "ssh": ("q95_ssh", "q95_ssh_tris"),
    "Hs":  ("q95_Hs", "q95_Hs_tris"),
    "tau": ("q95_tau", "q95_tau_tris"),
    "dz":  ("dz", "dz_tris"),
    "R1":  ("R1", "R1_tris"),
    "nveg": ("nveg", "nveg_tris"),
}

TILE_PROPERTY_NAMES: dict[str, str] = {
    "R1": "erosion_R1",
}

NODE_DIM = "nSCHISM_hgrid_node"

DEFAULT_TIPPECANOE = os.environ.get(
    "TIPPECANOE",
    "/gpfs/work/jacobb/miniforge3/envs/netcdf_tile_pipeline/bin/tippecanoe",
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--noveg-nc-dir", type=Path, required=True,
        help="indicator_nc/ from the vegetation-free run",
    )
    p.add_argument(
        "--veg-nc-dir", type=Path, required=True,
        help="indicator_nc/ from the with-vegetation run",
    )
    p.add_argument(
        "--output-nc-dir", type=Path, default=Path("diff/indicator_nc"),
        help="Output directory for diff NetCDF (default: diff/indicator_nc)",
    )
    p.add_argument(
        "--output-pmtiles-dir", type=Path, default=Path("diff/indicator_pmtiles"),
        help="Output directory for diff PMTiles (default: diff/indicator_pmtiles)",
    )
    p.add_argument(
        "--only", default=None,
        help="Process a single indicator key (ssh, Hs, tau, dz, R1, nveg)",
    )
    p.add_argument("--skip-pmtiles", action="store_true")
    p.add_argument("--skip-nc", action="store_true",
                   help="Tile existing diff NetCDF only (skip diff computation)")
    p.add_argument(
        "--tiles-script", type=Path, default=None,
        help="Path to schism_vector_tiles_triangles.py",
    )
    p.add_argument(
        "--schism-utils", type=Path, default=Path(SCHISM_UTILS_DEFAULT),
        help="Path to schism-hereon-utilities (for --coords schism)",
    )
    p.add_argument(
        "--rundir", type=Path, default=None,
        help="SCHISM case directory for schism_setup() (default: cwd)",
    )
    p.add_argument(
        "--tippecanoe", default=None,
        help="Path to tippecanoe binary (default: TIPPECANOE env var or HPC default)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Tippecanoe resolution (same logic as discussed)
# ---------------------------------------------------------------------------

def _resolve_tippecanoe(explicit: str | Path | None = None) -> str:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("TIPPECANOE"):
        candidates.append(Path(os.environ["TIPPECANOE"]))
    candidates.append(Path(sys.executable).resolve().parent / "tippecanoe")
    candidates.append(Path(DEFAULT_TIPPECANOE))

    for p in candidates:
        if p.is_file():
            return str(p.resolve())

    found = shutil.which("tippecanoe")
    if found:
        return found

    raise FileNotFoundError(
        "tippecanoe not found. Install in the active env, set TIPPECANOE env var, "
        "or pass --tippecanoe."
    )


# ---------------------------------------------------------------------------
# Triangle tiles script resolution
# ---------------------------------------------------------------------------

def _resolve_tiles_script(override: Path | None) -> Path:
    if override is not None:
        path = override.expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Tiles script not found: {path}")
        return path
    for raw in (
        DEFAULT_TILES_SCRIPT,
        Path.cwd() / "schism_vector_tiles_triangles.py",
    ):
        path = raw.resolve()
        if path.is_file():
            return path
    raise FileNotFoundError(
        "schism_vector_tiles_triangles.py not found. Pass --tiles-script explicitly."
    )


def _triangle_script_capabilities(path: Path) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8")
    return {
        "geojson_property": "--geojson-property" in text,
        "no_tiny_polygon_reduction": "--no-tiny-polygon-reduction" in text,
        "tippecanoe_flag": "--tippecanoe" in text,
    }


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------

def compute_diff_nc(
    noveg_path: Path,
    veg_path: Path,
    output_path: Path,
    nc_var: str,
) -> None:
    """Compute diff = with_veg − no_veg for a single indicator NetCDF."""
    with xr.open_dataset(noveg_path) as ds_nv, xr.open_dataset(veg_path) as ds_v:
        if nc_var not in ds_nv:
            raise KeyError(f"{nc_var!r} not in {noveg_path}")
        if nc_var not in ds_v:
            raise KeyError(f"{nc_var!r} not in {veg_path}")

        vals_nv = ds_nv[nc_var].values.astype(np.float64)
        vals_v = ds_v[nc_var].values.astype(np.float64)

        if vals_nv.shape != vals_v.shape:
            raise ValueError(
                f"Shape mismatch for {nc_var}: no_veg {vals_nv.shape} vs "
                f"with_veg {vals_v.shape}. Same mesh required."
            )

        diff = vals_v - vals_nv

        n_finite = int(np.count_nonzero(np.isfinite(diff)))
        vmin = float(np.nanmin(diff)) if n_finite > 0 else float("nan")
        vmax = float(np.nanmax(diff)) if n_finite > 0 else float("nan")
        max_abs = float(np.nanmax(np.abs(diff))) if n_finite > 0 else float("nan")
        print(
            f"  {nc_var}: diff range [{vmin:.4f}, {vmax:.4f}] "
            f"({n_finite:,} finite nodes)"
        )
        if max_abs == 0.0:
            print(
                f"  WARNING: {nc_var} difference is identically zero. "
                "Check that no_veg and with_veg NetCDF files are from different runs."
            )

        # Build output in one shot — assigning SCHISM_hgrid_node_x/y after
        # Dataset creation triggers xarray MergeError (coord vs data_var ambiguity).
        data_vars: dict[str, Any] = {
            nc_var: ([NODE_DIM], diff.astype(np.float32)),
        }
        coords: dict[str, Any] = {}

        if "SCHISM_hgrid_face_nodes" in ds_nv:
            data_vars["SCHISM_hgrid_face_nodes"] = ds_nv["SCHISM_hgrid_face_nodes"]

        for cname in ("SCHISM_hgrid_node_x", "SCHISM_hgrid_node_y"):
            if cname in ds_nv.coords:
                coords[cname] = ds_nv.coords[cname]
            elif cname in ds_nv:
                # Stored as data_var in some indicator files — keep as coord
                coords[cname] = ([NODE_DIM], np.asarray(ds_nv[cname].values))

        # Preserve node dimension coordinate if present
        if NODE_DIM in ds_nv.coords:
            coords[NODE_DIM] = ds_nv.coords[NODE_DIM]

        ds_out = xr.Dataset(
            data_vars=data_vars,
            coords=coords,
            attrs={
                "Conventions": "CF-1.8",
                "source": "compute_scenario_diff.py",
                "sign_convention": "with_veg minus no_veg",
            },
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        ds_out.to_netcdf(output_path)
        print(f"  Wrote {output_path}")


# ---------------------------------------------------------------------------
# PMTiles generation
# ---------------------------------------------------------------------------

def run_vector_tiles(
    *,
    tiles_script: Path,
    nc_path: Path,
    variable: str,
    pmtiles_path: Path,
    schism_utils: Path,
    rundir: Path,
    tippecanoe_bin: str | None = None,
    face_value: str = "mean",
    indicator_key: str | None = None,
) -> None:
    if not tiles_script.is_file():
        raise FileNotFoundError(f"Missing tile script: {tiles_script}")

    caps = _triangle_script_capabilities(tiles_script)

    geojson_path = pmtiles_path.with_suffix(".geojsonseq")
    tile_property = TILE_PROPERTY_NAMES.get(variable, variable)
    cmd = [
        sys.executable,
        str(tiles_script.resolve()),
        "--nc", str(nc_path.resolve()),
        "--variable", variable,
        "--coords", "schism",
        "--schism-utils", str(schism_utils.resolve()),
        "--face-value", face_value,
        "--geojson", str(geojson_path.resolve()),
        "--pmtiles", str(pmtiles_path.resolve()),
    ]
    if tile_property != variable and caps["geojson_property"]:
        cmd.extend(["--geojson-property", tile_property])
    if tippecanoe_bin and caps["tippecanoe_flag"]:
        cmd.extend(["--tippecanoe", tippecanoe_bin])

    pmtiles_path.parent.mkdir(parents=True, exist_ok=True)
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(rundir))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    rundir = args.rundir or Path.cwd()
    tippecanoe_bin = None
    tiles_script = None

    if not args.skip_pmtiles:
        tiles_script = _resolve_tiles_script(args.tiles_script)
        tippecanoe_bin = _resolve_tippecanoe(args.tippecanoe)
        print(f"Tiles script: {tiles_script}")
        print(f"Tippecanoe:   {tippecanoe_bin}")

    processed = 0
    for key, (nc_var, pmtiles_stem) in INDICATOR_EXPORTS.items():
        if args.only is not None and args.only != key:
            continue

        nc_filename = f"{nc_var}.nc"
        diff_nc_path = args.output_nc_dir / nc_filename

        # --- Diff NetCDF ---
        if not args.skip_nc:
            noveg_nc = args.noveg_nc_dir / nc_filename
            veg_nc = args.veg_nc_dir / nc_filename

            if not noveg_nc.is_file():
                print(f"Skipping {key}: missing {noveg_nc}")
                continue
            if not veg_nc.is_file():
                print(f"Skipping {key}: missing {veg_nc}")
                continue

            print(f"\n{'='*60}")
            print(f"Computing diff for: {key} ({nc_var})")
            print(f"  no_veg:   {noveg_nc}")
            print(f"  with_veg: {veg_nc}")
            compute_diff_nc(noveg_nc, veg_nc, diff_nc_path, nc_var)
        else:
            if not diff_nc_path.is_file():
                print(f"Skipping {key}: missing diff NetCDF {diff_nc_path}")
                continue

        # --- Diff PMTiles ---
        if not args.skip_pmtiles:
            assert tiles_script is not None
            pmtiles_path = args.output_pmtiles_dir / f"{pmtiles_stem}.pmtiles"
            run_vector_tiles(
                tiles_script=tiles_script,
                nc_path=diff_nc_path,
                variable=nc_var,
                pmtiles_path=pmtiles_path,
                schism_utils=args.schism_utils,
                rundir=rundir,
                tippecanoe_bin=tippecanoe_bin,
                face_value="max" if key == "R1" else "mean",
                indicator_key=key,
            )

        processed += 1

    if processed == 0:
        print("\nNo indicators processed. Check that indicator_nc/ folders exist "
              "and contain matching files.")
    else:
        print(f"\n{'='*60}")
        print(f"Done — processed {processed} indicator(s)")
        print(f"  Diff NetCDF:  {args.output_nc_dir}")
        if not args.skip_pmtiles:
            print(f"  Diff PMTiles: {args.output_pmtiles_dir}")


if __name__ == "__main__":
    main()
