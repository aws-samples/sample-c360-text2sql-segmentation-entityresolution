import os
import boto3
import json
import uuid
import logging
import time
from datetime import datetime

DATASET_GROUP_ARN = os.environ["DATASET_GROUP_ARN"]
DATASET_ARN = os.environ["DATASET_ARN"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
OUTPUT_PREFIX = os.environ["OUTPUT_PREFIX"]
PERSONALIZE_ROLE_ARN = os.environ["PERSONALIZE_ROLE_ARN"]
USER_PER_SEGMENT = os.environ.get("USER_PER_SEGMENT", "100")
SOLUTION_VERSION_TABLE = os.environ["SOLUTION_VERSION_TABLE"]
ATHENA_DATABASE = os.environ["ATHENA_DATABASE"]  # Athenaデータベース名
ATHENA_OUTPUT_LOCATION = os.environ["ATHENA_OUTPUT_LOCATION"]  # Athenaクエリ結果の出力先
ATHENA_WORKGROUP = os.environ["ATHENA_WORKGROUP"]  # Athenaワークグループ

s3 = boto3.client("s3")
personalize = boto3.client("personalize")
dynamodb = boto3.resource("dynamodb")
athena = boto3.client("athena")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def check_existing_items(item_ids):
    """
    item_based_segmentテーブルに既に存在するitem_idをチェックする

    Args:
        item_ids: チェックするitem_idのリスト

    Returns:
        既に存在するitem_idのリスト
    """
    if not item_ids:
        return []

    try:
        # item_idのリストをカンマ区切りの文字列に変換
        item_ids_str = ", ".join([f"'{item_id}'" for item_id in item_ids])

        # Athenaクエリを実行
        query = f"SELECT DISTINCT item_id FROM item_based_segment WHERE item_id IN ({item_ids_str})"
        logger.info(f"Executing Athena query: {query}")

        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": ATHENA_DATABASE},
            ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_LOCATION},
            WorkGroup=ATHENA_WORKGROUP,
        )

        query_execution_id = response["QueryExecutionId"]

        # クエリの完了を待つ
        query_status = wait_for_query_completion(query_execution_id)

        if query_status == "SUCCEEDED":
            # クエリ結果を取得
            results = athena.get_query_results(QueryExecutionId=query_execution_id)

            # 結果からitem_idを抽出
            existing_items = []

            # 最初の行はヘッダーなのでスキップ
            for row in results["ResultSet"]["Rows"][1:]:
                if "Data" in row and row["Data"]:
                    item_id = row["Data"][0].get("VarCharValue")
                    if item_id:
                        existing_items.append(item_id)

            logger.info(f"Found {len(existing_items)} existing items: {existing_items}")
            return existing_items
        else:
            logger.error(f"Athena query failed with status: {query_status}")
            return []

    except Exception as e:
        logger.error(f"Error checking existing items: {str(e)}")
        return []


def wait_for_query_completion(query_execution_id):
    """
    Athenaクエリの完了を待つ

    Args:
        query_execution_id: クエリ実行ID

    Returns:
        クエリの最終状態（'SUCCEEDED', 'FAILED', 'CANCELLED'など）
    """

    max_retries = 60
    retry_count = 0

    while retry_count < max_retries:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = response["QueryExecution"]["Status"]["State"]
        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            logger.info("response of athena")
            logger.info(response)

            return state

        retry_count += 1
        time.sleep(3)  # 3秒待機

    return "TIMEOUT"


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
        # Get item_ids from the event
        item_ids = event.get("item_ids", [])

        if not item_ids:
            raise ValueError("item_ids is required and cannot be empty")

        logger.info(f"Creating segment for item_ids: {item_ids}")

        # 既存のitem_idをチェック
        existing_items = check_existing_items(item_ids)

        # 既存のitem_idを除外
        new_item_ids = [item_id for item_id in item_ids if item_id not in existing_items]

        if not new_item_ids:
            logger.info("All requested item_ids already exist in item_based_segment table. No new segments to create.")
            return {
                "message": "All requested item_ids already exist in item_based_segment table. No new segments created.",
                "isCompleted": True,
                "existingItems": existing_items,
            }

        logger.info(f"Creating segments for {len(new_item_ids)} new items: {new_item_ids}")
        logger.info(f"Skipping {len(existing_items)} existing items: {existing_items}")

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
        for item_id in new_item_ids:  # 新しいitem_idのみを使用
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
