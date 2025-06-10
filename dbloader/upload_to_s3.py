#!/usr/bin/env python3
import glob
import boto3
from pathlib import Path

S3_BUCKET_NAME = "<set bucket name here>"  # Replace with your actual bucket name

s3_client = boto3.client("s3")


def upload_files_to_s3():
    """
    Upload CSV files from dbloader/testdata to S3 bucket,
    organizing them in folders named after the files (without extension)
    """
    # Initialize S3 client

    # Get all CSV files in the dbloader/testdata directory
    csv_files = glob.glob("testdata/*.csv")

    if not csv_files:
        print("No CSV files found in dbloader/testdata directory")
        return

    print(f"Found {len(csv_files)} CSV files to upload")

    # Upload each file to its corresponding folder in S3
    for csv_file in csv_files:
        # Get the filename without extension to use as folder name
        file_path = Path(csv_file)
        file_name = file_path.stem  # Gets filename without extension

        # Define the S3 key (path in the bucket)
        s3_key = f"input/{file_name}/{file_path.name}"

        print(f"Uploading {csv_file} to s3://{S3_BUCKET_NAME}/{s3_key}")

        try:
            # Upload the file to S3
            s3_client.upload_file(Filename=csv_file, Bucket=S3_BUCKET_NAME, Key=s3_key)
            print(f"Successfully uploaded {file_path.name} to s3://{S3_BUCKET_NAME}/{s3_key}")
        except Exception as e:
            print(f"Error uploading {file_path.name}: {str(e)}")


if __name__ == "__main__":
    print(f"Starting upload to S3 bucket: {S3_BUCKET_NAME}")
    upload_files_to_s3()
    print("Upload process completed")
