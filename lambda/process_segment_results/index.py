import os
import boto3
import json
import csv
import logging
import tempfile
from datetime import datetime

# Get environment variables (all required)
SEGMENT_BUCKET = os.environ["SEGMENT_BUCKET"]  # Batch segment job output bucket
SEGMENT_PREFIX = os.environ["SEGMENT_PREFIX"]  # Batch segment job output prefix
TARGET_BUCKET = os.environ["TARGET_BUCKET"]  # Bucket to store processed CSV results
TARGET_PREFIX = os.environ["TARGET_PREFIX"]  # Prefix to store processed CSV results

s3 = boto3.client("s3")
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda function to:
    1. Read the batch segment job results from S3
    2. Convert the JSON format to CSV format
    3. Save the CSV file to the data bucket (洗い替え方式)

    Args:
        event: The event dict from Step Functions containing the batch segment job details
        context: Lambda context
    """
    try:
        # Get parameters from event
        params = extract_parameters(event)

        # Delete existing CSV files (replacement method)
        delete_existing_csv_files(params["target_bucket"], params["target_prefix"])

        # Process JSON files and convert to CSV
        process_segment_files(params["source_bucket"], params["source_prefix"], params["target_bucket"], params["target_key"])

        logger.info(f"Successfully processed segment results and created CSV file: {params['csv_filename']}")

    except Exception as e:
        logger.error(f"Error processing segment results: {str(e)}")
        raise


def extract_parameters(event):

    job_name = event.get("jobName")
    batch_segment_job_arn = event.get("batchSegmentJobArn")

    if not job_name:
        raise ValueError("jobName is required in the event payload")

    segment_output_path = f"s3://{SEGMENT_BUCKET}/{SEGMENT_PREFIX}output/{job_name}/"

    logger.info(f"Processing segment results from: {segment_output_path}")

    s3_path = segment_output_path.replace("s3://", "")
    source_bucket = s3_path.split("/")[0]
    source_prefix = "/".join(s3_path.split("/")[1:])

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    csv_filename = f"segment_results_{timestamp}.csv"
    target_key = f"{TARGET_PREFIX}{csv_filename}"

    return {
        "job_name": job_name,
        "segment_output_path": segment_output_path,
        "source_bucket": source_bucket,
        "source_prefix": source_prefix,
        "csv_filename": csv_filename,
        "target_bucket": TARGET_BUCKET,
        "target_prefix": TARGET_PREFIX,
        "target_key": target_key,
    }


def process_segment_files(source_bucket, source_prefix, target_bucket, target_key):
    file_count = 0
    total_user_count = 0
    logger.info(f"bucket is {source_bucket} key is {source_prefix}")

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".csv") as temp_csv:
        csv_writer = csv.writer(temp_csv)
        csv_writer.writerow(["item_id", "user_id"])

        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=source_bucket, Prefix=source_prefix)

        for page in pages:
            if "Contents" not in page:
                continue

            for obj in page.get("Contents", []):
                key = obj["Key"]

                if key.endswith(".json.out"):
                    logger.info(f"Processing file: {key}")
                    file_count += 1

                    user_count = process_json_file_streaming(source_bucket, key, temp_csv, csv_writer)
                    total_user_count += user_count

    if file_count == 0:
        os.unlink(temp_csv.name)
        raise Exception("No valid segment data files found in the output location")

    temp_csv_path = temp_csv.name
    with open(temp_csv_path, "rb") as f:
        s3.put_object(Bucket=target_bucket, Key=target_key, Body=f.read(), ContentType="text/csv")

    logger.info(f"CSV file uploaded to: s3://{target_bucket}/{target_key}")
    logger.info(f"Processed {file_count} files and {total_user_count} users")


def process_json_file_streaming(source_bucket, source_key, temp_csv_file, csv_writer):
    """
    S3のJSONファイルをストリーミング処理し、CSVファイルに追記する

    Args:
        source_bucket: ソースバケット名
        source_key: ソースオブジェクトキー
        temp_csv_file: 一時CSVファイルオブジェクト
        csv_writer: CSVライターオブジェクト

    Returns:
        処理したユーザーの総数
    """
    # 一時ファイルにJSONをダウンロード
    with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as temp_json:
        s3.download_fileobj(source_bucket, source_key, temp_json)

    # ユーザー数をカウント
    user_count = 0

    try:
        # ダウンロードしたJSONファイルを読み込み
        with open(temp_json.name, "r") as json_file:
            # 各行を処理
            for line in json_file:
                if line.strip():
                    try:
                        # JSONとして解析
                        data = json.loads(line)

                        # 入力アイテムIDと出力ユーザーリストを取得
                        item_id = data.get("input", {}).get("itemId")
                        users_list = data.get("output", {}).get("usersList", [])

                        if item_id and users_list:
                            # 各ユーザーIDに対して行を追加
                            for user_id in users_list:
                                csv_writer.writerow([item_id, user_id])
                                user_count += 1
                    except json.JSONDecodeError as e:
                        logger.warning(f"Error parsing JSON line: {e}")
    finally:
        # 一時JSONファイルを削除
        os.unlink(temp_json.name)

    logger.info(f"Processed {user_count} users from {source_key}")
    return user_count


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
