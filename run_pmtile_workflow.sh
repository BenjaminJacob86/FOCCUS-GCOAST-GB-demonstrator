#!/usr/bin/env bash
# ==========================================================================
# Full scenario PMTiles pipeline: no_veg + with_veg + diff → upload to Edito
#
# Run from one of the scenario run directories (or any dir on HPC).
# Assumes both SCHISM runs share the same mesh and the same date range.
#
# Usage:
#   bash run_pmtile_workflow.sh                    # default: today's date
#   bash run_pmtile_workflow.sh 2026-08-01         # specific start date
#   bash run_pmtile_workflow.sh 2026-08-01 3       # 3 forecast days
#   SKIP_UPLOAD=1 bash run_pmtile_workflow.sh      # skip S3 upload
#   SKIP_DIFF=1 bash run_pmtile_workflow.sh        # skip diff computation
#   DRY_RUN=1 bash run_pmtile_workflow.sh          # print commands, don't run
# ==========================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — adjust paths to match your HPC layout
# ---------------------------------------------------------------------------

# Two SCHISM run directories (each with outputs/ containing out2d_*.nc)
NOVEG_RUNDIR="/gpfs/work/ksddata/ROUTINES_personal/SCHISM/gb_wave_routine"
VEG_RUNDIR="/gpfs/work/ksddata/ROUTINES_personal/SCHISM/gb_wave_routine_seagrass"

# Processing code and helper scripts live in tile_test/
TILE_TEST="${NOVEG_RUNDIR}/tile_test"

# Conda environment with Python libs (xarray, numpy, schism-hereon-utilities)
CONDA_ENV="/gpfs/home/jacobb/miniforge3/envs/netcdf_tile_pipeline"

# Tippecanoe binary (may be in a different env — see home vs work issue)
TIPPECANOE="/gpfs/work/jacobb/miniforge3/envs/netcdf_tile_pipeline/bin/tippecanoe"

# SCHISM utilities path (for schism_setup())
SCHISM_UTILS="/gpfs/work/ksddata/code/schism/scripts/schism-hereon-utilities/"

# Forecast date range
START_DATE="${1:-$(date +%Y-%m-%d)}"
N_DAYS="${2:-3}"

# Upload scripts
UPLOAD_NOVEG="${TILE_TEST}/EDITO_upload_persistent_json_credentials_today_vegfree.py"
UPLOAD_VEG="${TILE_TEST}/EDITO_upload_persistent_json_credentials_today_vegetation.py"
UPLOAD_DIFF="${TILE_TEST}/EDITO_upload_persistent_json_credentials_today_diff.py"

# Export for child processes
export TIPPECANOE

# ---------------------------------------------------------------------------
# Derived paths
# ---------------------------------------------------------------------------

python="${CONDA_ENV}/bin/python"
export PATH="${CONDA_ENV}/bin:$(dirname "${TIPPECANOE}"):${PATH}"

EROSION_SCRIPT="${TILE_TEST}/Erosion_risk_vector_tiles_for_streamlit.py"
DIFF_SCRIPT="${TILE_TEST}/compute_scenario_diff.py"

# Output directories per scenario
NOVEG_NC="${NOVEG_RUNDIR}/indicator_nc"
NOVEG_PM="${NOVEG_RUNDIR}/indicator_pmtiles"
VEG_NC="${VEG_RUNDIR}/indicator_nc"
VEG_PM="${VEG_RUNDIR}/indicator_pmtiles"
DIFF_NC="${VEG_RUNDIR}/diff/indicator_nc"
DIFF_PM="${VEG_RUNDIR}/diff/indicator_pmtiles"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() { echo -e "\n\033[1;36m[$(date +%H:%M:%S)] $*\033[0m"; }

run_cmd() {
    echo "+ $*"
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        echo "  (dry run — skipped)"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

log "Pre-flight checks"
echo "  Python:     ${python}"
echo "  Tippecanoe: ${TIPPECANOE}"
echo "  Start date: ${START_DATE}"
echo "  Days:       ${N_DAYS}"

for f in "${python}" "${TIPPECANOE}" "${EROSION_SCRIPT}"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Missing $f" >&2
        exit 1
    fi
done

if [[ ! -f "${DIFF_SCRIPT}" ]] && [[ "${SKIP_DIFF:-0}" != "1" ]]; then
    echo "WARNING: ${DIFF_SCRIPT} not found — diff step will be skipped"
    SKIP_DIFF=1
fi

echo "  Erosion script: ${EROSION_SCRIPT}"
echo "  Diff script:    ${DIFF_SCRIPT}"
"${python}" --version
"${TIPPECANOE}" --version 2>&1 | head -1

# ---------------------------------------------------------------------------
# Step 1: Symlink model output (both scenarios)
# ---------------------------------------------------------------------------

log "Step 1: Linking model output NetCDF for ${N_DAYS} days from ${START_DATE}"

link_outputs() {
    local rundir="$1"
    local tile_dir="$2"
    local src_dir="${rundir}/outputs"

    cd "${tile_dir}"
    for d in $(seq 0 $((N_DAYS - 1))); do
        date_str=$(date --date="${START_DATE} +${d} day" +"%Y%m%d")
        ncfile="out2d_${date_str}.nc"
        src="${src_dir}/${ncfile}"
        if [[ -L "${ncfile}" ]]; then
            rm -f "${ncfile}"
        fi
        if [[ -f "${src}" ]]; then
            ln -sf "${src}" .
            echo "  Linked: ${ncfile}"
        else
            echo "  WARNING: ${src} not found — skipping"
        fi
    done
}

mkdir -p "${TILE_TEST}"
link_outputs "${NOVEG_RUNDIR}" "${TILE_TEST}"

# For the seagrass run, create a parallel tile_test if needed
VEG_TILE_TEST="${VEG_RUNDIR}/tile_test"
mkdir -p "${VEG_TILE_TEST}"
# Copy processing scripts if not present
for script in Erosion_risk_vector_tiles_for_streamlit.py \
              schism_vector_tiles_triangles.py \
              compute_scenario_diff.py; do
    if [[ -f "${TILE_TEST}/${script}" ]] && [[ ! -f "${VEG_TILE_TEST}/${script}" ]]; then
        cp "${TILE_TEST}/${script}" "${VEG_TILE_TEST}/"
    fi
done

link_outputs "${VEG_RUNDIR}" "${VEG_TILE_TEST}"

# ---------------------------------------------------------------------------
# Step 2: Compute indicators — no_veg scenario
# ---------------------------------------------------------------------------

log "Step 2a: Computing indicators (vegetation-free)"
cd "${TILE_TEST}"
run_cmd "${python}" "${EROSION_SCRIPT}" \
    --nc-glob 'out2d_*.nc' \
    --output-nc-dir "${NOVEG_NC}" \
    --output-pmtiles-dir "${NOVEG_PM}" \
    --tippecanoe "${TIPPECANOE}"

# ---------------------------------------------------------------------------
# Step 3: Compute indicators — with_veg scenario
# ---------------------------------------------------------------------------

log "Step 2b: Computing indicators (with vegetation)"
cd "${VEG_TILE_TEST}"
run_cmd "${python}" "${EROSION_SCRIPT}" \
    --nc-glob 'out2d_*.nc' \
    --output-nc-dir "${VEG_NC}" \
    --output-pmtiles-dir "${VEG_PM}" \
    --tippecanoe "${TIPPECANOE}"

# ---------------------------------------------------------------------------
# Step 4: Compute scenario diff
# ---------------------------------------------------------------------------

if [[ "${SKIP_DIFF:-0}" != "1" ]]; then
    log "Step 3: Computing scenario differences (with_veg − no_veg)"
    cd "${TILE_TEST}"
    run_cmd "${python}" "${DIFF_SCRIPT}" \
        --noveg-nc-dir "${NOVEG_NC}" \
        --veg-nc-dir "${VEG_NC}" \
        --output-nc-dir "${DIFF_NC}" \
        --output-pmtiles-dir "${DIFF_PM}" \
        --schism-utils "${SCHISM_UTILS}" \
        --tippecanoe "${TIPPECANOE}"
else
    log "Step 3: SKIPPED (SKIP_DIFF=1)"
fi

# ---------------------------------------------------------------------------
# Step 5: Upload to Edito S3
# ---------------------------------------------------------------------------

if [[ "${SKIP_UPLOAD:-0}" != "1" ]]; then
    log "Step 4: Uploading to Edito"

    if [[ -f "${UPLOAD_NOVEG}" ]]; then
        log "  Uploading vegetation-free scenario"
        cd "${TILE_TEST}"
        run_cmd "${python}" "${UPLOAD_NOVEG}"
    else
        echo "  WARNING: ${UPLOAD_NOVEG} not found — skipping no_veg upload"
    fi

    if [[ -f "${UPLOAD_VEG}" ]]; then
        log "  Uploading with-vegetation scenario"
        cd "${TILE_TEST}"
        run_cmd "${python}" "${UPLOAD_VEG}"
    else
        echo "  WARNING: ${UPLOAD_VEG} not found — skipping with_veg upload"
    fi

    if [[ -f "${UPLOAD_DIFF}" ]]; then
        log "  Uploading scenario-diff folder"
        cd "${TILE_TEST}"
        # Positional YYYYMMDD — same CLI style as vegetation uploader
        date_yyyymmdd=$(date --date="${START_DATE}" +"%Y%m%d")
        run_cmd "${python}" "${UPLOAD_DIFF}" "${date_yyyymmdd}"
    else
        echo "  WARNING: ${UPLOAD_DIFF} not found — skipping diff upload"
        echo "    Diff NC:      ${DIFF_NC}"
        echo "    Diff PMTiles: ${DIFF_PM}"
        echo "    S3 target:    s3://project-foccus/Hereon/ESC1/YYYYMMDD/diff/"
    fi
else
    log "Step 4: SKIPPED (SKIP_UPLOAD=1)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

log "Pipeline complete"
echo ""
echo "Output directories:"
echo "  no_veg  NC:      ${NOVEG_NC}"
echo "  no_veg  PMTiles: ${NOVEG_PM}"
echo "  with_veg NC:     ${VEG_NC}"
echo "  with_veg PMTiles:${VEG_PM}"
echo "  diff     NC:     ${DIFF_NC}"
echo "  diff     PMTiles:${DIFF_PM}"
echo ""
echo "Folder structure on Edito (per date):"
echo "  YYYYMMDD/no_veg/   ← ${NOVEG_PM}/*.pmtiles + ${NOVEG_NC}/*.nc"
echo "  YYYYMMDD/with_veg/ ← ${VEG_PM}/*.pmtiles + ${VEG_NC}/*.nc"
echo "  YYYYMMDD/diff/     ← ${DIFF_PM}/*.pmtiles + ${DIFF_NC}/*.nc  (seagrass − no_veg)"
