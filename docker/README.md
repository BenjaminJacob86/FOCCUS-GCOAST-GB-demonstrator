# Docker — FOCCUS SCHISM PMTiles viewer

Containerized Streamlit app for the German Bight / ESC1 demonstrator.
Data is loaded at runtime from public Edito MinIO (`project-foccus` / `Hereon/ESC1`).

## Quick start (Windows)

```bat
cd docker
build.bat
run.bat
```

Open **http://localhost:8501**

## Quick start (Linux / Mac)

```bash
cd docker
bash build.sh
docker run --rm -p 8501:8501 foccus-pmtiles-viewer
```

## Visual Port / port mapping

| Host | Container | Service |
|------|-----------|---------|
| `8501` | `8501` | Streamlit UI |

Same pattern as the Grid_Plus_Forcing Visual Port app (`-p 8501:8501`).

Example detached run:

```bat
docker run -d -p 8501:8501 --name foccus-pmtiles-viewer foccus-pmtiles-viewer
```

## Files

| File | Role |
|------|------|
| `Dockerfile` | Image definition (`python:3.13-slim` + Streamlit app) |
| `build.bat` / `build.sh` | Pre-pull base image, then build |
| `run.bat` | Interactive run on port 8501 |

Build **context** is the repository root (`..`). Only app + config + About assets are copied into the image (see `Dockerfile` `COPY` lines and root `.dockerignore`).

## Config

Default: `APP_CONFIG=config/german_bight.yaml` (scenarios `no_veg` / `with_veg` / `diff`).

Override at runtime:

```bat
docker run --rm -p 8501:8501 -e APP_CONFIG=config/black_sea_douglas.yaml foccus-pmtiles-viewer
```

## Healthcheck

`GET http://localhost:8501/_stcore/health`

## Notes

- No SCHISM NetCDF / PMTiles are baked into the image.
- HPC upload / tippecanoe scripts are **not** included (viewer only).
- If Docker Hub pull fails, download the base once: `docker pull python:3.13-slim`, then re-run `build.bat`.
