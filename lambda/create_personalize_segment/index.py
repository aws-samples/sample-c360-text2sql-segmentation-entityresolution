import os
import boto3
import json
import time
import uuid
import logging

DATASET_GROUP_ARN = os.environ["DATASET_GROUP_ARN"]
DATASET_ARN = os.environ["DATASET_ARN"]
ATHENA_BUCKET = os.environ["ATHENA_BUCKET"]
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
OUTPUT_PREFIX = os.environ["OUTPUT_PREFIX"]
GLUE_DATABASE_NAME = os.environ["GLUE_DATABASE_NAME"]
PERSONALIZE_ROLE_ARN = os.environ["PERSONALIZE_ROLE_ARN"]
USER_PER_SEGMENT = os.environ.get("USER_PER_SEGMENT", "100")

athena = boto3.client("athena")
s3 = boto3.client("s3")
personalize = boto3.client("personalize")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to:
    1. Query Glue table to get all item IDs from the main brand item master
    2. Create a batch segment job in Amazon Personalize using the Item Affinity recipe
       with proper JSON format for input data

    Args:
        event: The event dict from Step Functions containing the solution version ARN
        context: Lambda context

    Returns:
        Dictionary containing job details and status
    """
    try:
        # Get solution version ARN from the event
        solution_version_arn = event.get("solutionVersionArn")

        logger.info(f"Using solution version ARN: {solution_version_arn}")

        # Generate unique ID for this run using UUID
        unique_id = str(uuid.uuid4())
        execution_id = unique_id

        # SQL query to get all item IDs from the main brand item master
        query = f"""
        SELECT 
            item_id
        FROM 
            {GLUE_DATABASE_NAME}.item_master
        """

        logger.info(f"Executing Athena query: {query}")

        # Start Athena query execution
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": GLUE_DATABASE_NAME},
            ResultConfiguration={
                "OutputLocation": f"s3://{ATHENA_BUCKET}/athena-results/{execution_id}/",
                "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"},
            },
            WorkGroup="primary",
        )

        query_execution_id = response["QueryExecutionId"]
        logger.info(f"Started Athena query with execution ID: {query_execution_id}")

        # Wait for query to complete
        state = "RUNNING"
        while state in ["RUNNING", "QUEUED"]:
            response = athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = response["QueryExecution"]["Status"]["State"]

            if state in ["RUNNING", "QUEUED"]:
                time.sleep(5)

        if state == "FAILED":
            error_message = response["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
            raise Exception(f"Athena query failed: {error_message}")
        elif state == "CANCELLED":
            raise Exception("Athena query was cancelled")

        logger.info("Athena query completed successfully")

        # Get the S3 path of the query results
        result_location = response["QueryExecution"]["ResultConfiguration"]["OutputLocation"]
        logger.info(f"Athena query results stored at: {result_location}")

        # Parse the S3 path to get bucket and key
        s3_path = result_location.replace("s3://", "")
        s3_bucket = s3_path.split("/")[0]
        s3_key = "/".join(s3_path.split("/")[1:])

        # Read the CSV results from S3
        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        csv_content = response["Body"].read().decode("utf-8")

        # Skip header row and process each item ID
        lines = csv_content.strip().split("\n")
        item_ids = [line.strip('"') for line in lines[1:] if line.strip()]

        logger.info(f"Found {len(item_ids)} item IDs")

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

        return {
            "jobName": job_name,
            "batchSegmentJobArn": batch_segment_job_arn,
            "athenaQueryExecutionId": query_execution_id,
            "inputLocation": input_s3_path,
            "isCompleted": False,
            "message": f"Batch segment job created successfully: {job_name}",
            "uniqueId": unique_id,
        }

    except Exception as e:
        logger.error(f"Error creating batch segment job: {str(e)}")
        raise
