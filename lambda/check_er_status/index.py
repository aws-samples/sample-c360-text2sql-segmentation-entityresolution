import boto3
import json
import logging
import os

WORKFLOW_NAME = os.environ["WORKFLOW_NAME"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)
er_client = boto3.client("entityresolution")


def handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    job_id = event["jobId"]
    try:
        response = er_client.get_matching_job(workflowName=WORKFLOW_NAME, jobId=job_id)
        status = response["status"]
        logger.info(f"job {job_id} status: {status}")

        if status == "FAILED":
            error_msg = response.get("errorDetails", {"errorMessage": "Unknown reason"}).get("errorMessage", "Unknown reason")
            logger.error(error_msg)
            raise Exception(error_msg)

        is_completed = status == "SUCCEEDED"

        result = {"isCompleted": is_completed, **event}

        return result

    except Exception as e:
        logger.error(f"Error checking job status: {str(e)}")
        raise
