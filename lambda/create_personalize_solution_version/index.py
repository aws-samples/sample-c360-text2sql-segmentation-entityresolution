import boto3


personalize = boto3.client("personalize")


def handler(event, context):
    """
    Lambda function to create a Personalize solution version.
    This function starts the creation process but does not wait for completion.

    Args:
        event: The event dict from Step Functions
        context: Lambda context

    Returns:
        Dictionary containing solution version details and status
    """
    try:
        # Get solution ARN from the event
        solution_arn = event.get("solutionArn")

        # Create the solution version
        response = personalize.create_solution_version(solutionArn=solution_arn)

        solution_version_arn = response["solutionVersionArn"]

        return {
            "solutionVersionArn": solution_version_arn,
            "isCompleted": False,
        }

    except Exception as e:
        print(f"Error creating solution version: {str(e)}")
        raise
