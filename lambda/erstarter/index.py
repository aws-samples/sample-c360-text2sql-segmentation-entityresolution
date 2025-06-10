import json
import boto3
import os
import logging

WORKFLOW_NAME = os.environ["WORKFLOW_NAME"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)
er_client = boto3.client("entityresolution")


def handler(event, context):
    try:
        # Execute matching workflow
        logger.info(f"Starting matching workflow: {WORKFLOW_NAME}")
        response = er_client.start_matching_job(workflowName=WORKFLOW_NAME)
        job_id = response["jobId"]
        logger.info(f"Started matching job with ID: {job_id}")

        return {"jobId": job_id}
    except Exception as e:
        logger.error(f"Error running entity resolution: {e}")
        return {"statusCode": 500, "body": json.dumps(f"Error running entity resolution: {str(e)}")}
