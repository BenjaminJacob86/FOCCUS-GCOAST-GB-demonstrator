@echo off
REM Build the FOCCUS PMTiles Streamlit viewer image (Visual Port / local Docker).
REM Run this script from the docker\ folder.
REM Build context is the repository root (parent of docker\).

set IMAGE_NAME=foccus-pmtiles-viewer
set BASE_IMAGE=python:3.13-slim

echo Checking if %BASE_IMAGE% is already downloaded...
docker image inspect %BASE_IMAGE% >nul 2>&1
if errorlevel 1 (
    echo.
    echo %BASE_IMAGE% not found locally
    echo Attempting to download %BASE_IMAGE% - this may take a while
    echo If this fails due to network issues, try:
    echo   1. Check your internet connection
    echo   2. Try again later when network is stable
    echo   3. Use a VPN if behind a firewall
    echo   4. Manually download: docker pull %BASE_IMAGE%
    echo.
    docker pull %BASE_IMAGE%
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to download %BASE_IMAGE%
        echo This is likely a network connectivity issue with Docker Hub
        echo.
        echo Checking for any existing python images that might work...
        docker images python* 2>nul
        echo.
        echo Please resolve the network issue and try again
        echo Or manually pull: docker pull %BASE_IMAGE%
        exit /b 1
    )
    echo %BASE_IMAGE% downloaded successfully
) else (
    echo %BASE_IMAGE% found locally, using cached image
)

echo.
echo Building FOCCUS PMTiles viewer image...
REM Context = parent directory (app sources live at repo root)
docker build -f Dockerfile -t %IMAGE_NAME% ..

if errorlevel 1 (
    echo ERROR: Build failed
    exit /b 1
)

echo.
echo Build complete - Image tagged as: %IMAGE_NAME%
echo.
echo Run with:
echo   run.bat
echo   or: docker run --rm -p 8501:8501 %IMAGE_NAME%
echo Then open http://localhost:8501
