import os
import boto3
import json
import uuid
import logging
from datetime import datetime

DATASET_GROUP_ARN = os.environ["DATASET_GROUP_ARN"]
DATASET_ARN = os.environ["DATASET_ARN"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
OUTPUT_PREFIX = os.environ["OUTPUT_PREFIX"]
PERSONALIZE_ROLE_ARN = os.environ["PERSONALIZE_ROLE_ARN"]
USER_PER_SEGMENT = os.environ.get("USER_PER_SEGMENT", "100")
SOLUTION_VERSION_TABLE = os.environ["SOLUTION_VERSION_TABLE"]
TARGET_BUCKET = os.environ["TARGET_BUCKET"]  # Bucket to store processed CSV results
TARGET_PREFIX = os.environ["TARGET_PREFIX"]  # Prefix to store processed CSV results

s3 = boto3.client("s3")
personalize = boto3.client("personalize")
dynamodb = boto3.resource("dynamodb")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def delete_existing_csv_files(bucket, prefix):
    """
    指定したバケットとプレフィックスに一致するCSVファイルを全て削除する

    Args:
        bucket: S3バケット名
        prefix: S3オブジェクトプレフィックス
    """
    try:
        # Paginatorを使用して全てのオブジェクトを取得
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        # 削除対象のオブジェクトを収集
        objects_to_delete = []

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page.get("Contents", []):
                key = obj["Key"]

                # CSVファイルのみを対象にする
                if key.endswith(".csv"):
                    objects_to_delete.append({"Key": key})

        # オブジェクトを削除
        if objects_to_delete:
            logger.info(f"Deleting {len(objects_to_delete)} existing CSV files")

            # S3のdelete_objectsは1000オブジェクトまでしか一度に削除できないため、
            # 1000オブジェクトごとにバッチ処理
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i : i + 1000]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})

            logger.info(f"Successfully deleted {len(objects_to_delete)} existing CSV files")
    except Exception as e:
        logger.error(f"Error deleting existing CSV files: {str(e)}")
        # 削除に失敗しても処理は続行


def handler(event, context):
    """
    Lambda function to create a batch segment job in Amazon Personalize using the Item Affinity recipe
    with proper JSON format for input data.

    Args:
        event: The event dict containing item_ids (list)
        context: Lambda context

    Returns:
        Dictionary containing job details and status
    """
    try:
        # Delete existing CSV files (replacement method)
        logger.info(f"Deleting existing CSV files from {TARGET_BUCKET}/{TARGET_PREFIX}")
        delete_existing_csv_files(TARGET_BUCKET, TARGET_PREFIX)

        # Get item_ids from the event
        item_ids = event.get("item_ids", [])

        if not item_ids:
            raise ValueError("item_ids is required and cannot be empty")

        logger.info(f"Creating segment for item_ids: {item_ids}")

        # Get solution version ARN from DynamoDB and update segment job status
        try:
            logger.info(f"Getting solution version ARN from DynamoDB table: {SOLUTION_VERSION_TABLE}")
            solution_version_table = dynamodb.Table(SOLUTION_VERSION_TABLE)
            response = solution_version_table.get_item(Key={"id": "latest"})

            if "Item" in response and "solutionVersionArn" in response["Item"]:
                solution_version_arn = response["Item"]["solutionVersionArn"]
                logger.info(f"Retrieved solution version ARN from DynamoDB: {solution_version_arn}")
            else:
                raise ValueError("No solution version ARN found in DynamoDB")
        except Exception as ddb_error:
            logger.error(f"Error retrieving solution version ARN from DynamoDB: {str(ddb_error)}")
            raise

        logger.info(f"Using solution version ARN: {solution_version_arn}")

        # Generate unique ID for this run using UUID
        unique_id = str(uuid.uuid4())

        # Create JSON input file in the correct format for batch segment job
        # Each line should be in format: {"itemId": "ITEM_ID"}
        json_input = []
        for item_id in item_ids:
            json_input.append(json.dumps({"itemId": item_id}))

        # Join with newlines to create the proper input format
        json_content = "\n".join(json_input)

        # Upload the JSON file to S3
        input_key = f"{OUTPUT_PREFIX}input/{unique_id}.json"
        s3.put_object(Bucket=OUTPUT_BUCKET, Key=input_key, Body=json_content.encode("utf-8"), ContentType="application/json")

        input_s3_path = f"s3://{OUTPUT_BUCKET}/{input_key}"
        logger.info(f"Uploaded batch segment input to: {input_s3_path}")

        # Create a unique job name with UUID
        job_name = unique_id

        # Create the batch segment job using the properly formatted JSON input
        response = personalize.create_batch_segment_job(
            jobName=job_name,
            solutionVersionArn=solution_version_arn,
            numResults=int(USER_PER_SEGMENT),
            jobInput={"s3DataSource": {"path": input_s3_path}},
            jobOutput={
                "s3DataDestination": {
                    "path": f"s3://{OUTPUT_BUCKET}/{OUTPUT_PREFIX}output/{job_name}/",
                }
            },
            roleArn=PERSONALIZE_ROLE_ARN,
        )

        batch_segment_job_arn = response["batchSegmentJobArn"]

        logger.info(f"Created batch segment job: {job_name} with ARN: {batch_segment_job_arn}")

        # Update segment job status in DynamoDB
        try:
            logger.info(f"Updating segment job status in DynamoDB table: {SOLUTION_VERSION_TABLE}")
            solution_version_table.update_item(
                Key={"id": "latest"},
                UpdateExpression="SET segmentJobId = :jobId, segmentJobStatus = :status, segmentJobItemIds = :itemIds, segmentJobCreatedAt = :createdAt",
                ExpressionAttributeValues={
                    ":jobId": job_name,
                    ":status": "RUNNING",
                    ":itemIds": item_ids,
                    ":createdAt": datetime.now().isoformat(),
                },
            )
            logger.info("Successfully updated segment job status in DynamoDB")
        except Exception as ddb_error:
            logger.error(f"Error updating segment job status in DynamoDB: {str(ddb_error)}")
            # Continue even if update fails

        return {
            "jobName": job_name,
            "batchSegmentJobArn": batch_segment_job_arn,
            "inputLocation": input_s3_path,
            "isCompleted": False,
            "message": f"Batch segment job created successfully: {job_name}",
            "uniqueId": unique_id,
        }

    except Exception as e:
        logger.error(f"Error creating batch segment job: {str(e)}")
        raise
