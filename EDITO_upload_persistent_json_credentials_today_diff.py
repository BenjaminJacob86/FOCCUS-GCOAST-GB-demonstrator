#!/usr/bin/env python3
"""
Upload scenario-diff indicator NetCDF + PMTiles to Edito MinIO.

Same pattern as:
  EDITO_upload_persistent_json_credentials_today_vegfree.py
  EDITO_upload_persistent_json_credentials_today_vegetation.py

Target:
  s3://project-foccus/Hereon/ESC1/{YYYYMMDD}/diff/

Example::

  python EDITO_upload_persistent_json_credentials_today_diff.py
  python EDITO_upload_persistent_json_credentials_today_diff.py 20260801
"""

import argparse
import datetime as dt
import json
import os
from glob import glob

import boto3

# ==============================
# LOAD CREDENTIALS
# ==============================

with open("/gpfs/work/ksddata/EDITO/stac_upload/credentials.json", "r") as f:
    creds = json.load(f)

ACCESS_KEY = creds["accessKey"]
SECRET_KEY = creds["secretKey"]

# ==============================
# CONFIG
# ==============================

MINIO_ENDPOINT = "https://minio.dive.edito.eu"
BUCKET_NAME = "project-foccus"

# Diff outputs live under the seagrass run (with_veg − no_veg)
folders = [
    "/gpfs/work/ksddata/ROUTINES_personal/SCHISM/gb_wave_routine_seagrass/diff/indicator_nc/",
    "/gpfs/work/ksddata/ROUTINES_personal/SCHISM/gb_wave_routine_seagrass/diff/indicator_pmtiles/",
]

# ------------------------------
# Optional date argument (YYYYMMDD)
# ------------------------------
parser = argparse.ArgumentParser(
    description="Upload diff indicator_nc + indicator_pmtiles to Edito (…/YYYYMMDD/diff/)"
)
parser.add_argument(
    "date",
    nargs="?",
    help="Upload date in YYYYMMDD format (default: today)",
)
args = parser.parse_args()

if args.date:
    try:
        date = dt.datetime.strptime(args.date, "%Y%m%d").strftime("%Y%m%d")
    except ValueError:
        raise SystemExit("Error: date must be in YYYYMMDD format.")
else:
    date = dt.datetime.today().strftime("%Y%m%d")

# MUST end with '/' — avoid double slash after date
TARGET_FOLDER = f"Hereon/ESC1/{date}/diff/"

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

# Ensure "folder" exists (empty object key)
s3.put_object(Bucket=BUCKET_NAME, Key=TARGET_FOLDER)
print(f"Folder ensured: s3://{BUCKET_NAME}/{TARGET_FOLDER}")

for ifolder, folder in enumerate(folders):
    print(folder)
    if not os.path.isdir(folder):
        print(f"  WARNING: directory not found — skipping: {folder}")
        continue

    if ifolder == 0:
        FILE_PATTERNS = ["*.nc", "*.npz"]
    else:
        FILE_PATTERNS = ["*.pmtiles"]

    os.chdir(folder)

    for FILE_PATTERN in FILE_PATTERNS:
        for local_path in glob(FILE_PATTERN):
            filename = os.path.basename(local_path)
            remote_key = TARGET_FOLDER + filename
            s3.upload_file(local_path, BUCKET_NAME, remote_key)
            print(f"Uploaded: {local_path} → s3://{BUCKET_NAME}/{remote_key}")
