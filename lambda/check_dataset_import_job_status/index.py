import boto3
import logging

personalize = boto3.client("personalize")
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to check the status of a Personalize dataset import job.

    Args:
        event: The event dict from Step Functions containing the dataset import job ARN
        context: Lambda context

    Returns:
        Dictionary containing dataset import job status and completion flag
    """
    try:
        # Get dataset import job ARN from the event
        dataset_import_job_arn = event.get("datasetImportJobArn")

        logger.info(f"Checking status for dataset import job: {dataset_import_job_arn}")

        # Get the dataset import job status
        response = personalize.describe_dataset_import_job(datasetImportJobArn=dataset_import_job_arn)

        status = response["datasetImportJob"]["status"]
        logger.info(f"Current dataset import job status: {status}")

        # Check if the dataset import job is completed
        is_completed = status == "ACTIVE"

        if status == "CREATE FAILED":
            failure_reason = response["datasetImportJob"].get("failureReason", "Unknown reason")
            logger.error(f"Dataset import job failed: {failure_reason}")
            raise Exception(f"Dataset import job failed: {failure_reason}")

        return {
            "datasetImportJobArn": dataset_import_job_arn,
            "status": status,
            "isCompleted": is_completed,
        }

    except Exception as e:
        logger.error(f"Error checking dataset import job status: {str(e)}")
        raise
