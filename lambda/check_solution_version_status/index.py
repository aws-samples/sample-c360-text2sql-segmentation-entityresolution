import boto3
import logging
import os

personalize = boto3.client("personalize")
dynamodb = boto3.resource("dynamodb")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get the table name from environment variables
SOLUTION_VERSION_TABLE = os.environ["SOLUTION_VERSION_TABLE"]
solution_version_table = dynamodb.Table(SOLUTION_VERSION_TABLE)


def handler(event, context):
    """
    Lambda function to check the status of a Personalize solution version.
    If the solution version is ACTIVE, it also stores the ARN in DynamoDB.

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

        # If solution version is ACTIVE, store the ARN in DynamoDB
        if is_completed:
            try:
                logger.info(f"Storing solution version ARN in DynamoDB table: {SOLUTION_VERSION_TABLE}")

                # Store the solution version ARN in DynamoDB
                # We use a fixed ID 'latest' to always update the same record
                solution_version_table.put_item(
                    Item={
                        "id": "latest",
                        "solutionVersionArn": solution_version_arn,
                        "segmentJobStatus": "NONE",  # Initialize segment job status
                    }
                )
                logger.info("Successfully stored solution version ARN in DynamoDB")
            except Exception as ddb_error:
                logger.error(f"Error storing solution version ARN in DynamoDB: {str(ddb_error)}")
                # We don't want to fail the entire function if DynamoDB update fails
                # Just log the error and continue

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
