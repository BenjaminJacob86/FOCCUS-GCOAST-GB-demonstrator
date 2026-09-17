# FOCCUS SCHISM PMTiles viewer — Streamlit app for Visual Port / local Docker
#
# Build (from docker/):  build.bat
# Run:                   run.bat
# Open:                  http://localhost:8501
#
# Scientific data (PMTiles / NetCDF) is fetched at runtime from the public
# Edito MinIO bucket — nothing large is baked into the image.
#
# Build context is the repository root (parent of docker/).

FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal system libs. Geospatial wheels (netCDF4, h5py, shapely, …) ship
# their own native libs; curl is for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first for layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code, config, and About-page assets (filtered by root .dockerignore)
COPY . .

EXPOSE 8501

# Streamlit / Visual Port defaults — bind all interfaces, no browser prompt
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    APP_CONFIG=config/german_bight.yaml

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app_pmtiles_assessment_two_paged_s3.py", \
            "--server.port=8501", "--server.address=0.0.0.0"]
