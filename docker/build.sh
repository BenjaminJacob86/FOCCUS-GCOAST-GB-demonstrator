#!/usr/bin/env bash
# Build the FOCCUS PMTiles Streamlit viewer image.
# Run from the docker/ directory. Context is the repository root (..).

set -euo pipefail

IMAGE_NAME=foccus-pmtiles-viewer
BASE_IMAGE=python:3.13-slim

echo "Checking if ${BASE_IMAGE} is already downloaded..."
if docker image inspect "${BASE_IMAGE}" >/dev/null 2>&1; then
    echo "${BASE_IMAGE} found locally, using cached image"
else
    echo "Downloading ${BASE_IMAGE} (this may take a while)..."
    docker pull "${BASE_IMAGE}"
    echo "${BASE_IMAGE} downloaded successfully"
fi

echo ""
echo "Building FOCCUS PMTiles viewer image..."
docker build -f Dockerfile -t "${IMAGE_NAME}" ..

echo ""
echo "Build complete — Image tagged as: ${IMAGE_NAME}"
echo "Run: docker run --rm -p 8501:8501 ${IMAGE_NAME}"
echo "Open: http://localhost:8501"
