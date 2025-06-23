import boto3
import os
import logging

# 環境変数の取得
TARGET_BUCKET = os.environ["TARGET_BUCKET"]  # Bucket to store processed CSV results
TARGET_PREFIX = os.environ["TARGET_PREFIX"]  # Prefix to store processed CSV results

personalize = boto3.client("personalize")
s3 = boto3.client("s3")

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def delete_existing_csv_files(bucket, prefix):
    """
    指定したバケットとプレフィックスに一致するCSVファイルを全て削除する

    Args:
        bucket: S3バケット名
        prefix: S3オブジェクトプレフィックス
    """
    try:
        # Paginatorを使用して全てのオブジェクトを取得
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

        # 削除対象のオブジェクトを収集
        objects_to_delete = []

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page.get("Contents", []):
                key = obj["Key"]

                # CSVファイルのみを対象にする
                if key.endswith(".csv"):
                    objects_to_delete.append({"Key": key})

        # オブジェクトを削除
        if objects_to_delete:
            logger.info(f"Deleting {len(objects_to_delete)} existing CSV files")

            # S3のdelete_objectsは1000オブジェクトまでしか一度に削除できないため、
            # 1000オブジェクトごとにバッチ処理
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i : i + 1000]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})

            logger.info(f"Successfully deleted {len(objects_to_delete)} existing CSV files")
    except Exception as e:
        logger.error(f"Error deleting existing CSV files: {str(e)}")
        # 削除に失敗しても処理は続行


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
        # トレーニング開始時に既存のCSVファイルを削除
        logger.info(f"Deleting existing CSV files from {TARGET_BUCKET}/{TARGET_PREFIX}")
        delete_existing_csv_files(TARGET_BUCKET, TARGET_PREFIX)

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
