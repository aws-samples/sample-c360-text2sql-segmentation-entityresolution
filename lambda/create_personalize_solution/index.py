import os
import boto3
import time
import logging
from datetime import datetime
from operator import itemgetter

DATASET_GROUP_ARN = os.environ.get("DATASET_GROUP_ARN")
RECIPE_ARN = os.environ.get("RECIPE_ARN")

personalize = boto3.client("personalize")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to create a Personalize solution.
    This function starts the creation process but does not wait for completion.
    Before creating a new solution, it deletes older solutions, keeping only the 2 most recent ones.

    Args:
        event: The event dict from Step Functions
        context: Lambda context

    Returns:
        Dictionary containing solution details and status
    """
    try:
        existing_solutions = get_existing_solutions(DATASET_GROUP_ARN)
        logger.info(f"Found {len(existing_solutions)} existing solutions in dataset group")

        delete_old_solutions(existing_solutions)

        # Create a unique solution name with timestamp
        timestamp = int(time.time())
        solution_name = f"item-affinity-solution-{timestamp}"

        # Create the solution
        logger.info(f"Creating new solution: {solution_name}")
        response = personalize.create_solution(name=solution_name, datasetGroupArn=DATASET_GROUP_ARN, recipeArn=RECIPE_ARN)

        solution_arn = response["solutionArn"]
        logger.info(f"Created solution with ARN: {solution_arn}")

        return {
            "solutionArn": solution_arn,
            "solutionName": solution_name,
            "isCompleted": False,
            "timestamp": timestamp,
        }

    except Exception as e:
        logger.error(f"Error creating solution: {str(e)}")
        raise


def get_existing_solutions(dataset_group_arn):
    """
    指定されたDatasetGroup配下の既存のSolutionを取得する

    Args:
        dataset_group_arn: DatasetGroupのARN

    Returns:
        作成日時でソートされたSolutionのリスト（新しい順）
    """
    solutions = []
    next_token = None

    while True:
        if next_token:
            response = personalize.list_solutions(datasetGroupArn=dataset_group_arn, maxResults=100, nextToken=next_token)
        else:
            response = personalize.list_solutions(datasetGroupArn=dataset_group_arn, maxResults=100)

        for solution in response.get("solutions", []):
            solutions.append(
                {
                    "solutionArn": solution["solutionArn"],
                    "name": solution["name"],
                    "creationDateTime": solution["creationDateTime"],
                    "status": solution["status"],
                }
            )

        next_token = response.get("nextToken")
        if not next_token:
            break

    solutions.sort(key=itemgetter("creationDateTime"), reverse=True)

    return solutions


def delete_old_solutions(solutions):

    solutions_to_delete = solutions[2:]

    if not solutions_to_delete:
        logger.info("No old solutions to delete")
        return

    logger.info(f"Deleting {len(solutions_to_delete)} old solutions")

    for solution in solutions_to_delete:
        solution_arn = solution["solutionArn"]
        solution_name = solution["name"]

        try:
            logger.info(f"Deleting solution: {solution_name} ({solution_arn})")
            personalize.delete_solution(solutionArn=solution_arn)
            logger.info(f"Successfully deleted solution: {solution_name}")
        except Exception as e:
            logger.warning(f"Failed to delete solution {solution_name}: {str(e)}")
