import os
import boto3
import time
import uuid

DATASET_ARN = os.environ.get("DATASET_ARN")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")
GLUE_DATABASE_NAME = os.environ.get("GLUE_DATABASE_NAME")
PERSONALIZE_ROLE_ARN = os.environ.get("PERSONALIZE_ROLE_ARN")

athena = boto3.client("athena")
s3 = boto3.client("s3")
personalize = boto3.client("personalize")


def handler(event, context):
    """
    Lambda function to:
    1. Execute Athena query to JOIN purchase history with integrated customer data
    2. Create a dataset import job in Amazon Personalize

    Args:
        event: The event dict from Step Functions
        context: Lambda context

    Returns:
        Dictionary containing import job details and status
    """
    try:
        athena_output_location = f"s3://{OUTPUT_BUCKET}/athena-results/"
        unique_id = str(uuid.uuid4())
        execution_id = unique_id

        # SQL query to join purchase history with integrated customer data
        query = f"""
        -- Main brand purchase history
        SELECT 
            ic.MatchID as USER_ID,
            ph.item_id as ITEM_ID,
            ph.purchase_date as TIMESTAMP
        FROM 
            {GLUE_DATABASE_NAME}.purchase_history ph
        JOIN 
            {GLUE_DATABASE_NAME}.integrated_customer ic ON ph.customer_id = ic.RecordId
        
        UNION ALL
        
        -- Subbrand purchase history (item_idが重複した場合に備えて,item_idに"sub_"というプレフィックスを付与)
        SELECT 
            ic.MatchID as USER_ID,
            CONCAT('sub_', sph.item_id) as ITEM_ID,
            sph.purchase_date as TIMESTAMP
        FROM 
            {GLUE_DATABASE_NAME}.subbrand_purchase_history sph
        JOIN 
            {GLUE_DATABASE_NAME}.integrated_customer ic ON sph.customer_id = ic.RecordId
        """

        print(f"Executing Athena query: {query}")

        # Start Athena query execution
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": GLUE_DATABASE_NAME},
            ResultConfiguration={
                "OutputLocation": f"{athena_output_location}{execution_id}/",
                "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"},
            },
            WorkGroup="primary",
        )

        query_execution_id = response["QueryExecutionId"]
        print(f"Started Athena query with execution ID: {query_execution_id}")

        # Wait for query to complete
        state = "RUNNING"
        while state in ["RUNNING", "QUEUED"]:
            response = athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = response["QueryExecution"]["Status"]["State"]

            if state in ["RUNNING", "QUEUED"]:
                time.sleep(5)

        if state == "FAILED":
            error_message = response["QueryExecution"]["Status"].get("StateChangeReason", "Unknown error")
            raise Exception(f"Athena query failed: {error_message}")
        elif state == "CANCELLED":
            raise Exception("Athena query was cancelled")

        print("Athena query completed successfully")

        # Get the S3 path of the query results
        result_file = response["QueryExecution"]["ResultConfiguration"]["OutputLocation"]
        print(f"Athena query results stored at: {result_file}")

        # Create a unique import job name with timestamp
        job_name = unique_id

        # Create the dataset import job
        response = personalize.create_dataset_import_job(
            jobName=job_name, datasetArn=DATASET_ARN, dataSource={"dataLocation": result_file}, roleArn=PERSONALIZE_ROLE_ARN
        )

        dataset_import_job_arn = response["datasetImportJobArn"]

        print(f"Created dataset import job: {job_name} with ARN: {dataset_import_job_arn}")

        return {
            "jobName": job_name,
            "datasetImportJobArn": dataset_import_job_arn,
            "athenaQueryExecutionId": query_execution_id,
            "athenaResultLocation": result_file,
            "isCompleted": False,
        }

    except Exception as e:
        print(f"Error creating dataset import job: {str(e)}")
        raise
