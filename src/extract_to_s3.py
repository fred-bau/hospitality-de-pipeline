"""
Upload the raw Inside Airbnb files for each city from the local data/ folder to S3.

Expected local layout (one folder per city, city in every filename):
    data/<city>/<type>_<city>.csv.gz      e.g. data/paris/listings_paris.csv.gz

Uploaded to:
    s3://<bucket>/raw/<city>/<type>_<city>.csv.gz

Works both on your Mac and inside the Airflow container, because the data
folder is located relative to this script (src/../data).

Run from the project root:
    python src/extract_to_s3.py
"""
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()

# ---- Settings ----
CITIES = ["paris", "barcelona", "florence"]
FILE_TYPES = ["listings", "reviews", "calendar"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
S3_PREFIX = "raw"

AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")


def expected_files():
    """Every (city, local_path, s3_key) we expect. An explicit list, so a
    missing file is detected instead of silently skipped."""
    files = []
    for city in CITIES:
        for file_type in FILE_TYPES:
            filename = f"{file_type}_{city}.csv.gz"
            local_path = DATA_DIR / city / filename
            s3_key = f"{S3_PREFIX}/{city}/{filename}"
            files.append((city, local_path, s3_key))
    return files


def main():
    if not S3_BUCKET_NAME:
        raise RuntimeError("S3_BUCKET_NAME is not set (check your .env)")

    files = expected_files()

    # Fail loudly BEFORE uploading anything if any file is missing
    missing = [str(path) for _, path, _ in files if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "These expected files are missing:\n  " + "\n  ".join(missing)
        )

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=AWS_REGION,
    )

    print(f"Uploading {len(files)} files from {DATA_DIR} to s3://{S3_BUCKET_NAME}/{S3_PREFIX}/")
    for city, local_path, s3_key in files:
        local_size = local_path.stat().st_size
        print(f"  {local_path.relative_to(DATA_DIR)} ({local_size / 1e6:.1f} MB) -> {s3_key}")
        s3.upload_file(str(local_path), S3_BUCKET_NAME, s3_key)

        # Verify: the object in S3 must have exactly the same size as the local file
        remote_size = s3.head_object(Bucket=S3_BUCKET_NAME, Key=s3_key)["ContentLength"]
        if remote_size != local_size:
            raise RuntimeError(
                f"Size mismatch for {s3_key}: local {local_size} bytes, S3 {remote_size} bytes"
            )

    print(f"Done: {len(files)} files uploaded and verified.")


if __name__ == "__main__":
    main()