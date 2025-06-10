import os
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = os.environ.get("BUCKET_NAME")
SOURCE_PREFIX = os.environ.get("SOURCE_PREFIX")
DEST_PREFIX = os.environ.get("DEST_PREFIX")

s3 = boto3.client("s3")


def delete_existing_files(bucket, prefix):
    """
    Delete all existing files in the destination prefix
    """
    try:
        # List all objects in the destination prefix
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        objects_to_delete = []

        # Collect all objects to delete
        for page in pages:
            if "Contents" in page:
                for obj in page["Contents"]:
                    objects_to_delete.append({"Key": obj["Key"]})

        # Delete objects in batches of 1000 (S3 limit)
        if objects_to_delete:
            logger.info(f"Deleting {len(objects_to_delete)} existing files from {prefix}")

            # Process in batches of 1000
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i : i + 1000]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})

            logger.info(f"Successfully deleted existing files from {prefix}")
        else:
            logger.info(f"No existing files found in {prefix}")

    except ClientError as e:
        logger.error(f"Error deleting existing files: {e}")
        raise


def copy_files(bucket, source_job_prefix, dest_prefix):
    """
    Copy all files from source prefix to destination prefix
    """
    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=source_job_prefix)
        copied_count = 0
        logger.info(f"Copy from {source_job_prefix}")
        for page in pages:
            logger.info(" copy one file! ")
            logger.info(page)
            if "Contents" in page:
                for obj in page["Contents"]:
                    source_key = obj["Key"]
                    dest_key = source_key.replace(source_job_prefix, dest_prefix, 1)
                    s3.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": source_key}, Key=dest_key)
                    copied_count += 1

        logger.info(f"Successfully copied {copied_count} files to {dest_prefix}")

    except ClientError as e:
        logger.error(f"Error copying files: {e}")
        raise


def handler(event, context):

    try:
        job_id = event["jobId"]
        delete_existing_files(BUCKET_NAME, DEST_PREFIX)
        copy_files(BUCKET_NAME, f"{SOURCE_PREFIX.rstrip('/')}/{job_id}/success", DEST_PREFIX)

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        raise
