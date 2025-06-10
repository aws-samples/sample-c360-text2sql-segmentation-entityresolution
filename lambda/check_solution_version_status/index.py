import boto3
import logging

personalize = boto3.client("personalize")
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to check the status of a Personalize solution version.

    Args:
        event: The event dict from Step Functions containing the solution version ARN
        context: Lambda context

    Returns:
        Dictionary containing solution version status and completion flag
    """
    try:
        # Get solution version ARN from the event
        solution_version_arn = event.get("solutionVersionArn")

        logger.info(f"Checking status for solution version: {solution_version_arn}")

        # Get the solution version status
        response = personalize.describe_solution_version(solutionVersionArn=solution_version_arn)

        status = response["solutionVersion"]["status"]
        logger.info(f"Current solution version status: {status}")

        # Check if the solution version creation is completed
        is_completed = status == "ACTIVE"

        if status == "CREATE FAILED":
            failure_reason = response["solutionVersion"].get("failureReason", "Unknown reason")
            logger.error(f"Solution version creation failed: {failure_reason}")
            raise Exception(f"Solution version creation failed: {failure_reason}")

        return {
            "statusCode": 200,
            "solutionVersionArn": solution_version_arn,
            "status": status,
            "isCompleted": is_completed,
            "message": f"Solution version status: {status}",
        }

    except Exception as e:
        logger.error(f"Error checking solution version status: {str(e)}")
        raise
