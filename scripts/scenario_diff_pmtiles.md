# Scenario PMTiles — pipeline, diff computation, and upload layout

This document describes the full pipeline for producing **three scenario layers** (vegetation-free, with vegetation, and difference) as PMTiles + NetCDF for the Streamlit dashboard.

---

## 1. HPC folder structure

```
/gpfs/work/ksddata/ROUTINES_personal/SCHISM/
├── gb_wave_routine/                         ← no_veg SCHISM run
│   ├── outputs/                             ← raw SCHISM out2d_YYYYMMDD.nc
│   ├── tile_test/                           ← processing code + symlinked .nc
│   │   ├── Erosion_risk_vector_tiles_for_streamlit.py
│   │   ├── schism_vector_tiles_triangles.py
│   │   ├── compute_scenario_diff.py
│   │   ├── run_pmtile_workflow.sh
│   │   ├── EDITO_upload_persistent_json_credentials_today_vegfree.py
│   │   ├── EDITO_upload_persistent_json_credentials_today_vegetation.py
│   │   ├── EDITO_upload_persistent_json_credentials_today_diff.py
│   │   ├── hgrid.gr3 / hgrid.ll / sav_N.gr3
│   │   └── out2d_*.nc → ../outputs/out2d_*.nc  (symlinks)
│   ├── indicator_nc/                        ← no_veg indicator NetCDF
│   │   ├── q95_ssh.nc
│   │   ├── q95_Hs.nc
│   │   ├── q95_tau.nc
│   │   ├── R1.nc
│   │   └── nveg.nc
│   ├── indicator_pmtiles/                   ← no_veg PMTiles
│   │   ├── q95_ssh_tris.pmtiles
│   │   ├── q95_Hs_tris.pmtiles
│   │   └── ...
│
├── gb_wave_routine_seagrass/                ← with_veg SCHISM run
│   ├── outputs/
│   ├── tile_test/                           ← same scripts (copied or symlinked)
│   ├── indicator_nc/
│   ├── indicator_pmtiles/
│   └── diff/                                ← diff outputs (seagrass − no_veg)
│       ├── indicator_nc/
│       │   ├── q95_ssh.nc                   (= with_veg − no_veg)
│       │   └── ...
│       └── indicator_pmtiles/
│           ├── q95_ssh_tris.pmtiles
│           └── ...
```

---

## 2. S3 folder layout on Edito

For each forecast run date `YYYYMMDD`:

```
s3://oidc-jacobb/Hereon/IndicatorAssesment/
└── 20260801/
    ├── no_veg/
    │   ├── q95_ssh_tris.pmtiles
    │   ├── q95_ssh.nc
    │   ├── q95_Hs_tris.pmtiles
    │   ├── q95_Hs.nc
    │   └── ...
    ├── with_veg/
    │   ├── q95_ssh_tris.pmtiles
    │   ├── q95_ssh.nc
    │   └── ...
    └── diff/
        ├── q95_ssh_tris.pmtiles
        ├── q95_ssh.nc
        └── ...
```

| Subfolder | Content |
|-----------|---------|
| `no_veg/` | Vegetation-free reference simulation |
| `with_veg/` | Simulation with seagrass / NbS vegetation |
| `diff/` | **Precomputed difference** (with_veg − no_veg) per triangle |

**Filenames stay the same** inside each subfolder — only the parent folder changes.

---

## 3. Scripts

### `Erosion_risk_vector_tiles_for_streamlit.py`

Computes indicators from native SCHISM `out2d_*.nc` and produces indicator NetCDF + PMTiles.

```bash
cd /gpfs/work/.../gb_wave_routine/tile_test
python Erosion_risk_vector_tiles_for_streamlit.py \
  --nc-glob 'out2d_*.nc' \
  --output-nc-dir ../indicator_nc \
  --output-pmtiles-dir ../indicator_pmtiles \
  --tippecanoe /gpfs/work/jacobb/miniforge3/envs/netcdf_tile_pipeline/bin/tippecanoe
```

### `compute_scenario_diff.py`

Computes `diff = with_veg − no_veg` from the indicator NetCDF of both scenarios, then tiles the diff.

```bash
python compute_scenario_diff.py \
  --noveg-nc-dir  /gpfs/.../gb_wave_routine/indicator_nc \
  --veg-nc-dir    /gpfs/.../gb_wave_routine_seagrass/indicator_nc \
  --output-nc-dir ../diff/indicator_nc \
  --output-pmtiles-dir ../diff/indicator_pmtiles \
  --tippecanoe /gpfs/work/jacobb/miniforge3/envs/netcdf_tile_pipeline/bin/tippecanoe

# NetCDF only:
python compute_scenario_diff.py ... --skip-pmtiles

# One indicator:
python compute_scenario_diff.py ... --only ssh
```

### `run_pmtile_workflow.sh`

Master shell script that runs the full pipeline: symlink → no_veg → with_veg → diff → upload.

```bash
# Full pipeline for 3 days starting 2026-08-01
bash run_pmtile_workflow.sh 2026-08-01 3

# Dry run (print commands only)
DRY_RUN=1 bash run_pmtile_workflow.sh 2026-08-01

# Skip upload
SKIP_UPLOAD=1 bash run_pmtile_workflow.sh 2026-08-01

# Skip diff computation
SKIP_DIFF=1 bash run_pmtile_workflow.sh 2026-08-01
```

### `schism_vector_tiles_triangles.py`

Low-level script: single indicator NetCDF → GeoJSONSeq → tippecanoe → PMTiles. Called by the scripts above.

---

### `EDITO_upload_persistent_json_credentials_today_diff.py`

Same style as the vegfree / vegetation uploaders. Uploads from:

```text
…/gb_wave_routine_seagrass/diff/indicator_nc/
…/gb_wave_routine_seagrass/diff/indicator_pmtiles/
```

to:

```text
s3://project-foccus/Hereon/ESC1/YYYYMMDD/diff/
```

```bash
python EDITO_upload_persistent_json_credentials_today_diff.py           # today
python EDITO_upload_persistent_json_credentials_today_diff.py 20260801  # explicit date
```

Credentials: `/gpfs/work/ksddata/EDITO/stac_upload/credentials.json` (`accessKey` / `secretKey`).

`run_pmtile_workflow.sh` calls this in Step 4 after no_veg / with_veg uploads.

---

## 4. Difference sign convention


Use **`with_veg − no_veg`** consistently:

- **Negative** → indicator lower with vegetation (e.g. wave attenuation)
- **Positive** → higher with vegetation

### Colormap for diff maps

In YAML, the `diff` scenario sets `is_difference: true`. The app defaults to **`coolwarm`** and critical value **`0`** unless you override with `diff_cmap` / `diff_critical_default` on each indicator.

---

## 5. Enable scenarios in the app

1. Copy `config/german_bight_scenarios.example.yaml` → `config/german_bight.yaml` (or merge the `scenarios:` block).
2. Upload all three subfolders for at least one run date.
3. Run the app — a **Scenario** dropdown appears next to Run date.

Without a `scenarios:` block, behaviour is unchanged (flat `YYYYMMDD/` layout).

---

## 6. Tippecanoe path (home vs work conda)

If your shell's `conda activate` does not put tippecanoe on `PATH` (common when home and work have separate miniforge installs), use one of:

```bash
# Option A: export env var
export TIPPECANOE=/gpfs/work/jacobb/miniforge3/envs/netcdf_tile_pipeline/bin/tippecanoe

# Option B: pass --tippecanoe to each script
python Erosion_risk_vector_tiles_for_streamlit.py ... --tippecanoe $TIPPECANOE
python compute_scenario_diff.py ... --tippecanoe $TIPPECANOE

# Option C: run_pmtile_workflow.sh handles this automatically
```

---

## 7. Checklist per new run date

- [ ] Symlink `out2d_*.nc` in both `tile_test/` directories
- [ ] Run `Erosion_risk_vector_tiles_for_streamlit.py` for **no_veg**
- [ ] Run `Erosion_risk_vector_tiles_for_streamlit.py` for **with_veg**
- [ ] Run `compute_scenario_diff.py` → diff NetCDF + PMTiles
- [ ] Upload no_veg/, with_veg/, diff/ to Edito
- [ ] Test each scenario in the dashboard (map + polygon stats)

Or just: `bash run_pmtile_workflow.sh YYYY-MM-DD N_DAYS`

---

## 8. Notes

- **nveg** exists only in the with_veg scenario in many setups; the diff for nveg may be trivial (veg − 0 = veg). Consider skipping: `--only ssh` etc.
- **R1 diff** may need a dedicated interpretation (ratio differences); consider keeping R1 diff on a diverging scale centred at 0.
- Both scenarios **must share the same mesh topology** (same faces, same ordering). The diff script validates shape but not geometry.
- Keep PMTiles **min zoom** low enough (`-Z0`) so the full domain is visible at opening zoom.
