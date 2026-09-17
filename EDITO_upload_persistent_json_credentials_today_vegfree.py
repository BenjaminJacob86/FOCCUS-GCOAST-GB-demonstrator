import boto3
import os
import json
from glob import glob
import datetime as dt

# ==============================
# LOAD CREDENTIALS
# ==============================

with open("/gpfs/work/ksddata/EDITO/stac_upload/credentials.json", "r") as f:
    creds = json.load(f)

ACCESS_KEY = creds["accessKey"]
SECRET_KEY = creds["secretKey"]

# ==============================
# CONFIG �~@~T PUT YOUR KEYS HERE
# ==============================

MINIO_ENDPOINT = "https://minio.dive.edito.eu"


today=dt.datetime.today()

#date='20260604/'
date=today.strftime('%Y%m%d')+'/'
date='20260604/'



BUCKET_NAME = "project-foccus"
#TARGET_FOLDER = "/Hereon//"+date   # MUST end with '/'
TARGET_FOLDER = "/Hereon/ESC1/"+date +"/no_veg/"   # MUST end with '/'

#LOCAL_FILE = "./argo_fc/20251213_d-Hereon--DOXY-BLK-b20251212_fc.nc"
#FILE_PATTERN='*_cog.tif'



folders=['/gpfs/work/ksddata/ROUTINES_personal/SCHISM/gb_wave_routine/indicator_nc/','/gpfs/work/ksddata/ROUTINES_personal/SCHISM/gb_wave_routine/indicator_pmtiles/']

for ifolder,folder in enumerate(folders):
    print(folder)

    if ifolder==0:
        FILE_PATTERN='*.nc'
        FILE_PATTERN='*.npz'

        FILE_PATTERNS=['*.nc','*.npz']

    else:
        FILE_PATTERN='*.pmtiles'
        FILE_PATTERNS=['*.pmtiles',]

    os.chdir(folder)
    
    for FILE_PATTERN in FILE_PATTERNS:


        # ==============================
        # CREATE CLIENT
        # ==============================

        s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
        )


        # ==============================
        # ENSURE "FOLDER" EXISTS
        # ==============================

        # In S3/MinIO folders are just empty objects
        s3.put_object(Bucket=BUCKET_NAME, Key=TARGET_FOLDER)

        print(f"Folder ensured: s3://{BUCKET_NAME}/{TARGET_FOLDER}")

        # ==============================
        # UPLOAD FILE
        # ==============================
        for local_path in glob(FILE_PATTERN):
            filename = os.path.basename(local_path)
            remote_key = TARGET_FOLDER + filename

            s3.upload_file(local_path, BUCKET_NAME, remote_key)
            print(f"Uploaded: {local_path} → s3://{BUCKET_NAME}/{remote_key}")



