import os
import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-central-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

def upload_local_files_to_s3():
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    data_dir = "data"
    for root, _, files in os.walk(data_dir):
        for file in files:
            if file.endswith((".csv", ".csv.gz")) and "(" not in file:
                local_path = os.path.join(root, file)
                
                clean_name = file if file.endswith(".csv.gz") else f"{os.path.basename(root)}.csv"
                s3_key = f"raw/{clean_name}"
                
                print(f"Uploading {local_path} to s3://{S3_BUCKET_NAME}/{s3_key}...")
                s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
                print(f"Successfully uploaded {s3_key}")

if __name__ == "__main__":
    upload_local_files_to_s3()
    