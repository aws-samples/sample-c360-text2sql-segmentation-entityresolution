import boto3
import logging

personalize = boto3.client("personalize")
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to check the status of a Personalize batch segment job.

    Args:
        event: The event dict from Step Functions containing the batch segment job ARN
        context: Lambda context

    Returns:
        Dictionary containing batch segment job status and completion flag
    """
    try:
        # Get batch segment job ARN from the event
        batch_segment_job_arn = event.get("batchSegmentJobArn")
        job_name = event.get("jobName")

        logger.info(f"Checking status for batch segment job: {batch_segment_job_arn}")

        # Get the batch segment job status
        response = personalize.describe_batch_segment_job(batchSegmentJobArn=batch_segment_job_arn)

        status = response["batchSegmentJob"]["status"]
        logger.info(f"Current batch segment job status: {status}")

        # Check if the batch segment job is completed
        is_completed = status == "ACTIVE"

        if status == "CREATE FAILED":
            failure_reason = response["batchSegmentJob"].get("failureReason", "Unknown reason")
            logger.error(f"Batch segment job failed: {failure_reason}")
            raise Exception(f"Batch segment job failed: {failure_reason}")

        return {
            "batchSegmentJobArn": batch_segment_job_arn,
            "jobName": job_name,
            "status": status,
            "isCompleted": is_completed,
            "message": f"Batch segment job status: {status}",
        }

    except Exception as e:
        logger.error(f"Error checking batch segment job status: {str(e)}")
        raise
