import boto3
import logging

personalize = boto3.client("personalize")
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to check the status of a Personalize solution.

    Args:
        event: The event dict from Step Functions containing the solution ARN
        context: Lambda context

    Returns:
        Dictionary containing solution status and completion flag
    """
    try:
        # Get solution ARN from the event
        solution_arn = event.get("solutionArn")

        logger.info(f"Checking status for solution: {solution_arn}")

        # Get the solution status
        response = personalize.describe_solution(solutionArn=solution_arn)

        status = response["solution"]["status"]
        logger.info(f"Current solution status: {status}")

        # Check if the solution creation is completed
        is_completed = status == "ACTIVE"

        if status == "CREATE FAILED":
            failure_reason = response["solution"].get("failureReason", "Unknown reason")
            logger.error(f"Solution creation failed: {failure_reason}")
            raise Exception(f"Solution creation failed: {failure_reason}")

        return {
            "statusCode": 200,
            "solutionArn": solution_arn,
            "status": status,
            "isCompleted": is_completed,
            "message": f"Solution status: {status}",
        }

    except Exception as e:
        logger.error(f"Error checking solution status: {str(e)}")
        raise
