@echo off
REM Run the FOCCUS PMTiles viewer container (Streamlit on port 8501).
REM Matches Visual Port style: host 8501 → container 8501.

set IMAGE_NAME=foccus-pmtiles-viewer
set CONTAINER_NAME=foccus-pmtiles-viewer

REM Stop/remove an existing container with the same name (ignore errors)
docker rm -f %CONTAINER_NAME% >nul 2>&1

echo Starting %CONTAINER_NAME% on http://localhost:8501
echo Override config example:
echo   docker run --rm -p 8501:8501 -e APP_CONFIG=config/black_sea_douglas.yaml %IMAGE_NAME%
echo.

docker run --rm -it ^
  -p 8501:8501 ^
  -e APP_CONFIG=config/german_bight.yaml ^
  --name %CONTAINER_NAME% ^
  %IMAGE_NAME%
