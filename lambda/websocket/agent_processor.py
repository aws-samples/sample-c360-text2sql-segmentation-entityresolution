import boto3
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List

from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client("s3")
athena = boto3.client("athena")
dynamodb = boto3.resource("dynamodb")
glue = boto3.client("glue")
sfn = boto3.client("stepfunctions")

# Required environment variables
SESSION_TABLE = os.environ["SESSION_TABLE"]
ATHENA_DATABASE = os.environ["ATHENA_DATABASE"]
ATHENA_OUTPUT_LOCATION = os.environ["ATHENA_OUTPUT_LOCATION"]
ATHENA_WORKGROUP = os.environ["ATHENA_WORKGROUP"]
SEGMENT_STATE_MACHINE_ARN = os.environ["SEGMENT_STATE_MACHINE_ARN"]
SOLUTION_VERSION_TABLE = os.environ["SOLUTION_VERSION_TABLE"]

# DynamoDB tables
session_table = dynamodb.Table(SESSION_TABLE)

# Bedrock model setup
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0", temperature=0.0, boto_session=boto3.Session(region_name="us-west-2")
)

# SQL result threshold
SQL_RESULT_THRESHOLD = 300

# Agent instruction
AGENT_INSTRUCTION = """
You are an advanced SQL Assistant that helps users query data using Amazon Athena.

Your primary role is to:
1. Understand natural language requests about data
2. Convert these requests into proper SQL queries for Athena
3. Execute these queries and present the results in a clear, readable format
4. Explain the results when appropriate
5. Create Amazon Personalize item-based segments when requested

You have access to the following tools:
- execute_sql_query: Executes a SQL query on Athena and returns the results
- create_downloadable_url: Creates a downloadable URL for query results
- create_personalize_item_based_segment: Creates an item-based segment using Amazon Personalize's batch segment job
- check_personalize_segment_status: Checks the status of the Amazon Personalize batch segment job

When a user asks a question about data, follow this process:
1. Based on the table structure provided in your system prompt and the user's question, formulate an appropriate SQL query
2. Execute the query using execute_sql_query
3. Present the results in a clear, readable format
4. Explain what the results mean in the context of the user's question

When a user asks to create an item-based segment:
1. Use the create_personalize_item_based_segment tool with the item IDs
2. Tell the user to wait a few minutes before checking the status
3. DO NOT call any other tools right after create_personalize_item_based_segment and please just inform the user that the Personalize batch segment job has started and will take several minutes to complete and user should ask you about status later.
4. When the user asks later about the status, You should use the check_personalize_segment_status tool to check and inform them.
5. Once the Personalize batch segment job is complete (status is "COMPLETED"), the segment data will be available in the item_based_segment table


IMPORTANT ATHENA SQL TIP:
-  use the from_unixtime() function for unixtime.
  example: from_unixtime(1605793223) or from_unixtime(unix_timestamp_column)
- To know current timestamp, use current_timestamp.
  example: SELECT current_timestamp
- unix_timestamp() function is NOT supported and you can not use it.
  unix_timestamp(a_unixtime_column) <== Bad!! This does not work.
  unix_timestamp() <== Bad !! This does not work.

Warning:
- Please do not use unix_timestamp(). this is not supported.

Always maintain a conversational tone and refer to previous interactions when appropriate.
If the user refers to previous conversations, use that context to provide better answers.
"""


@tool
def execute_sql_query(sql_query: str) -> str:
    """
    Execute a SQL query on Amazon Athena.

    Args:
        sql_query: The SQL query to execute

    Returns:
        The query results as a formatted string, including the query_execution_id
    """
    try:
        logger.info(sql_query)
        response = athena.start_query_execution(
            QueryString=sql_query,
            QueryExecutionContext={"Database": ATHENA_DATABASE},
            ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_LOCATION},
            WorkGroup=ATHENA_WORKGROUP,
        )

        query_execution_id = response["QueryExecutionId"]
        # Wait for the query to complete
        query_status = wait_for_query_completion(query_execution_id)
        logger.info(f"Query Execution ID: {query_execution_id}, query_status: {query_status}")
        if query_status == "SUCCEEDED":
            # Get the query results
            results = get_query_results(query_execution_id)
            formatted_results = format_query_results(sql_query, results)

            # Add query_execution_id to the response
            return f"{formatted_results}\n\nQuery Execution ID: {query_execution_id}"
        else:
            return f"Query failed with status: {query_status}"

    except Exception as e:
        logger.error(f"Error executing SQL query: {str(e)}")
        return f"Error executing query: {str(e)}"


@tool
def create_downloadable_url(query_execution_id: str) -> str:
    """
    Create a downloadable file from Athena query results and generate a presigned URL.

    This tool takes a query_execution_id from a previously executed Athena query,
    locates the results file in S3, and generates a presigned URL for accessing it.

    Args:
        query_execution_id: The Athena query execution ID

    Returns:
        A presigned URL to access the query results
    """
    try:
        # Get the query execution details to find the S3 location
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)

        # Extract the S3 location of the results
        output_location = response["QueryExecution"]["ResultConfiguration"]["OutputLocation"]

        # Parse the S3 URI to get bucket and key
        if output_location.startswith("s3://"):
            s3_parts = output_location[5:].split("/", 1)
            if len(s3_parts) == 2:
                bucket_name = s3_parts[0]
                object_key = s3_parts[1]

                # Generate a presigned URL (valid for 1 hour)
                presigned_url = s3.generate_presigned_url(
                    "get_object", Params={"Bucket": bucket_name, "Key": object_key}, ExpiresIn=3600  # URL expires in 1 hour
                )

                logger.info(presigned_url)
                return presigned_url
            else:
                return f"Error: Invalid S3 path format in {output_location}"
        else:
            return f"Error: Output location is not an S3 URI: {output_location}"

    except Exception as e:
        logger.error(f"Error creating downloadable URL: {str(e)}")
        return f"Error creating downloadable URL: {str(e)}"


@tool
def create_personalize_item_based_segment(item_ids: List[str]) -> str:
    """
    Create an item-based segment using Amazon Personalize's batch segment job.

    This tool starts a Step Functions state machine that creates an Amazon Personalize batch segment job
    for the specified items and processes the results. Amazon Personalize uses machine learning to identify
    users who are likely to interact with these specific items based on their behavior patterns.

    The segment data will be available in the item_based_segment table after the batch segment job is complete.

    Args:
        item_ids: A list of item IDs to create Personalize item-based segments for

    Returns:
        A message indicating whether the Personalize batch segment job was started successfully
    """
    try:
        if not item_ids:
            return "Error: No item IDs provided"

        # Check if a segment job is already running
        logger.info(f"Checking if a segment job is already running in DynamoDB table: {SOLUTION_VERSION_TABLE}")
        solution_version_table = dynamodb.Table(SOLUTION_VERSION_TABLE)
        response = solution_version_table.get_item(Key={"id": "latest"})

        if "Item" in response and "segmentJobStatus" in response["Item"]:
            status = response["Item"]["segmentJobStatus"]
            if status == "RUNNING":
                created_at = response["Item"].get("segmentJobCreatedAt", "unknown time")
                item_ids_running = response["Item"].get("segmentJobItemIds", [])
                return f"Error: Another Amazon Personalize batch segment job is already running. Started at {created_at} for item IDs: {item_ids_running}. Please wait for this job to complete before starting a new one. You can check the status using the check_personalize_segment_status tool."

        logger.info(f"Creating Amazon Personalize item-based segment for item IDs: {item_ids}")

        # Start the segment state machine
        execution_input = {"item_ids": item_ids}

        response = sfn.start_execution(
            stateMachineArn=SEGMENT_STATE_MACHINE_ARN, name=f"SegmentJob-{str(uuid.uuid4())}", input=json.dumps(execution_input)
        )

        logger.info(f"Started Amazon Personalize batch segment job execution: {response['executionArn']}")

        return f"Amazon Personalize item-based segment creation has started successfully. This process will take several minutes to complete. Please wait for a few minutes, then use the check_personalize_segment_status tool to check if the segment creation is complete. Once complete, the segment data will be available in the item_based_segment table."

    except Exception as e:
        logger.error(f"Error creating Amazon Personalize item-based segment: {str(e)}")
        return f"Error creating Amazon Personalize item-based segment: {str(e)}"


@tool
def check_personalize_segment_status() -> str:
    """
    Check the status of the Amazon Personalize batch segment job.

    This tool queries the DynamoDB table to get the status of the latest Amazon Personalize batch segment job.
    Amazon Personalize batch segment jobs can take some time to complete, and this tool helps track their progress.

    Returns:
        A message indicating the status of the Amazon Personalize batch segment job
    """
    try:
        logger.info(f"Checking Amazon Personalize batch segment job status in DynamoDB table: {SOLUTION_VERSION_TABLE}")
        solution_version_table = dynamodb.Table(SOLUTION_VERSION_TABLE)
        response = solution_version_table.get_item(Key={"id": "latest"})

        if "Item" not in response:
            return "Error: No Amazon Personalize batch segment job information found"

        item = response["Item"]

        # Check if segment job information exists
        if "segmentJobStatus" not in item:
            return "No Amazon Personalize batch segment job has been created yet"

        status = item["segmentJobStatus"]

        if status == "NONE":
            return "No Amazon Personalize batch segment job has been created yet"
        elif status == "RUNNING":
            created_at = item.get("segmentJobCreatedAt", "unknown time")
            item_ids = item.get("segmentJobItemIds", [])
            return f"Amazon Personalize batch segment job is currently running. Started at {created_at}. Creating item-based segments for item IDs: {item_ids}"
        elif status == "COMPLETED":
            created_at = item.get("segmentJobCreatedAt", "unknown time")
            completed_at = item.get("segmentJobCompletedAt", "unknown time")
            item_ids = item.get("segmentJobItemIds", [])
            return f"Amazon Personalize batch segment job completed successfully at {completed_at}. Started at {created_at}. Created item-based segments for item IDs: {item_ids}. The segment data is now available in the item_based_segment table."
        elif status == "FAILED":
            error_msg = item.get("segmentJobErrorMessage", "Unknown error")
            return f"Amazon Personalize batch segment job failed: {error_msg}"
        else:
            return f"Amazon Personalize batch segment job status: {status}"

    except Exception as e:
        logger.error(f"Error checking Amazon Personalize batch segment job status: {str(e)}")
        return f"Error checking Amazon Personalize batch segment job status: {str(e)}"


def wait_for_query_completion(query_execution_id: str) -> str:
    """
    Wait for an Athena query to complete and return its final state.

    Args:
        query_execution_id: The ID of the query execution

    Returns:
        The final query state (e.g., 'SUCCEEDED', 'FAILED')
    """
    import time

    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        response = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = response["QueryExecution"]["Status"]["State"]

        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            return state

        retry_count += 1
        time.sleep(1)  # Wait for 1 second before checking again

    return "TIMEOUT"


def get_query_results(query_execution_id: str) -> Dict[str, Any]:
    """
    Get the results of a completed Athena query.

    Args:
        query_execution_id: The ID of the query execution

    Returns:
        The query results
    """
    return athena.get_query_results(QueryExecutionId=query_execution_id, MaxResults=SQL_RESULT_THRESHOLD + 1)


def format_query_results(sql_query: str, results: Dict[str, Any]) -> str:
    """
    Format Athena query results into a readable string.
    If the number of rows exceeds SQL_RESULT_THRESHOLD, suggest downloading the results as CSV.

    Args:
        sql_query: The SQL query that was executed
        results: The query results from Athena

    Returns:
        A formatted string representation of the results
    """
    try:
        rows = results["ResultSet"]["Rows"]

        if not rows:
            return "Query executed successfully, but returned no results."

        # Extract column names from the first row
        header = [col["VarCharValue"] for col in rows[0]["Data"]]

        # Check if the number of rows exceeds the threshold
        row_count = len(rows) - 1  # Subtract 1 for the header row

        # Format the results as a table
        output = [f"SQL Query: {sql_query}\n"]

        if row_count >= SQL_RESULT_THRESHOLD:
            output.append(f"Results: more than {row_count} rows returned (exceeds the threshold)")
            output.append(
                "\nThe result set is too large as a response to an Agent. Please explain using the preview and urge client to download the full results as CSV"
            )
            output.append("\nShowing first few rows as preview:")

            # Add header row
            header_str = " | ".join(header)
            output.append(header_str)
            output.append("-" * len(header_str))

            # Add only the first few rows as a preview
            preview_rows = min(20, row_count)  # Show at most 20 rows as preview
            for row in rows[1 : preview_rows + 1]:  # Skip header row
                row_data = []
                for col in row["Data"]:
                    if "VarCharValue" in col:
                        row_data.append(col["VarCharValue"])
                    else:
                        row_data.append("NULL")
                output.append(" | ".join(row_data))

            output.append("...")
            output.append(f"\nTo download the complete results, use create_downloadable_url with the query_execution_id provided below.")
        else:
            output.append(f"Results: {row_count} rows returned")

            # Add header row
            header_str = " | ".join(header)
            output.append(header_str)
            output.append("-" * len(header_str))

            # Add all data rows
            for row in rows[1:]:  # Skip header row
                row_data = []
                for col in row["Data"]:
                    if "VarCharValue" in col:
                        row_data.append(col["VarCharValue"])
                    else:
                        row_data.append("NULL")
                output.append(" | ".join(row_data))

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Error formatting query results: {str(e)}")
        return f"Error formatting results: {str(e)}"


def list_athena_tables() -> tuple:
    """
    List all available tables in the Athena database using AWS Glue API.
    Includes table descriptions/comments.

    Returns:
        A tuple containing:
        - A string with formatted table list for display
        - A list of table dictionaries with name and description
    """
    try:
        # Get all tables from Glue Data Catalog
        response = glue.get_tables(DatabaseName=ATHENA_DATABASE)

        if "TableList" not in response or not response["TableList"]:
            return f"No tables found in database '{ATHENA_DATABASE}'.", []

        # Extract table information
        tables = []
        for table in response["TableList"]:
            table_name = table["Name"]
            table_description = table.get("Description", "No description available")
            tables.append({"name": table_name, "description": table_description})

        # Format the results for display
        tables_info = []
        tables_info.append(f"Available tables in database '{ATHENA_DATABASE}':")
        tables_info.append("Table Name | Description")
        tables_info.append("----------|------------")

        for table in tables:
            tables_info.append(f"{table['name']} | {table['description']}")

        return "\n".join(tables_info), tables

    except Exception as e:
        logger.error(f"Error listing Athena tables: {str(e)}")
        return f"Error listing tables: {str(e)}", []


def describe_athena_table(table_name: str) -> str:
    """
    Describe the schema of a specific Athena table using AWS Glue API.
    Includes column descriptions/comments.

    Args:
        table_name: The name of the table to describe (without description)

    Returns:
        A string containing the detailed table schema with comments
    """
    try:
        # Get table details from Glue Data Catalog
        logger.info(f"Describing table: {table_name}")
        response = glue.get_table(DatabaseName=ATHENA_DATABASE, Name=table_name)
        logger.info(response)
        if "Table" not in response:
            return f"Table '{table_name}' not found in database '{ATHENA_DATABASE}'."

        table = response["Table"]

        # Format the results
        schema = []

        # Add table information
        schema.append(f"Schema for table '{table_name}':")
        table_description = table.get("Description", "No description available")
        schema.append(f"Table Description: {table_description}")
        schema.append("")

        # Add column information
        schema.append("Column Name | Data Type | Description")
        schema.append("------------|-----------|------------")

        # Get columns from StorageDescriptor
        if "StorageDescriptor" in table and "Columns" in table["StorageDescriptor"]:
            columns = table["StorageDescriptor"]["Columns"]
            for column in columns:
                column_name = column["Name"]
                column_type = column["Type"]
                column_comment = column.get("Comment", "No description available")
                schema.append(f"{column_name} | {column_type} | {column_comment}")

        # Add partition keys if any
        if "PartitionKeys" in table and table["PartitionKeys"]:
            schema.append("")
            schema.append("Partition Keys:")
            schema.append("Column Name | Data Type | Description")
            schema.append("------------|-----------|------------")

            for column in table["PartitionKeys"]:
                column_name = column["Name"]
                column_type = column["Type"]
                column_comment = column.get("Comment", "No description available")
                schema.append(f"{column_name} | {column_type} | {column_comment}")

        # Add additional table properties if available
        if "Parameters" in table and table["Parameters"]:
            schema.append("")
            schema.append("Table Properties:")
            for key, value in table["Parameters"].items():
                schema.append(f"{key}: {value}")

        return "\n".join(schema)

    except Exception as e:
        logger.error(f"Error describing Athena table: {str(e)}")
        return f"Error describing table: {str(e)}"


def get_all_table_information() -> str:
    """
    Get information about all available tables in the Athena database.
    This function lists all tables and describes their schemas.

    Returns:
        A string containing comprehensive information about all tables
    """
    try:
        # Get formatted table list and table data in one call
        tables_info, tables = list_athena_tables()

        if not tables:
            return tables_info  # This will be the "No tables found" message

        # Get schema information for each table
        all_schemas = []

        # Add the original table list with descriptions for the agent
        all_schemas.append(tables_info)
        all_schemas.append("\n\nDETAILED TABLE SCHEMAS:")

        for table in tables:
            table_name = table["name"]
            table_schema = describe_athena_table(table_name)
            all_schemas.append(f"\n{table_schema}")

        return "\n".join(all_schemas)
    except Exception as e:
        logger.error(f"Error getting table information: {str(e)}")
        return f"Error retrieving table information: {str(e)}"


def get_conversation_history(user_id: str, session_id: str) -> List[Dict]:
    """
    Retrieve conversation history for a specific user and session from DynamoDB.

    Args:
        user_id: The ID of the user
        session_id: The ID of the session

    Returns:
        A list of message dictionaries in the format expected by the Agent
    """
    try:
        response = session_table.get_item(Key={"user_id": user_id, "session_id": session_id})

        if "Item" in response and "messages" in response["Item"]:
            return response["Item"]["messages"]
        else:
            return []

    except Exception as e:
        logger.error(f"Error retrieving conversation history: {str(e)}")
        return []


def save_conversation_history(user_id: str, session_id: str, messages: List[Dict]) -> bool:
    """
    Save conversation history for a specific user and session to DynamoDB.

    Args:
        user_id: The ID of the user
        session_id: The ID of the session
        messages: The list of message dictionaries from the Agent

    Returns:
        True if successful, False otherwise
    """
    try:
        session_table.put_item(
            Item={"user_id": user_id, "session_id": session_id, "messages": messages, "last_updated": datetime.now().isoformat()}
        )
        return True

    except Exception as e:
        logger.error(f"Error saving conversation history: {str(e)}")
        return False


def filter_messages_for_response(messages):
    """
    Filter and process messages for client response, maintaining original message order.

    This function processes the conversation messages and handles special cases:
    - Keeps regular conversation messages
    - Converts downloadable URL tool results to special URL messages
    - Filters out other tool use and tool result messages

    Args:
        messages: List of message dictionaries from the conversation

    Returns:
        List of filtered messages in their original order
    """
    filtered_messages = []
    tool_use_map = {}

    # First pass: identify all downloadable URL tool uses
    for message in messages:
        for content_item in message.get("content", []):
            if "toolUse" in content_item and content_item["toolUse"].get("name") == "create_downloadable_url":
                tool_use_id = content_item["toolUse"].get("toolUseId")
                if tool_use_id:
                    tool_use_map[tool_use_id] = True

    # Second pass: process messages in original order
    for message in messages:
        contents = message.get("content", [])

        # Check if this is a regular message (no tool use/result)
        if all("toolUse" not in item and "toolResult" not in item for item in contents):
            filtered_messages.append(message)
            continue

        # Check for downloadable URL tool result
        for content_item in contents:
            if "toolResult" in content_item and content_item["toolResult"].get("toolUseId") in tool_use_map:
                # Create and add special URL message
                url_text = content_item["toolResult"]["content"][0].get("text", "")
                filtered_messages.append({"role": "url", "content": [{"text": url_text}]})
                break

    return filtered_messages


def send_to_connection(connection_id, data, api_gateway_endpoint):
    """
    Send a message to a WebSocket connection.

    Args:
        connection_id: The WebSocket connection ID
        data: The data to send (will be converted to JSON)
        api_gateway_endpoint: The API Gateway endpoint URL
    """
    gateway_api = boto3.client("apigatewaymanagementapi", endpoint_url=api_gateway_endpoint)

    try:
        gateway_api.post_to_connection(ConnectionId=connection_id, Data=json.dumps(data).encode("utf-8"))
    except Exception as e:
        logger.error(f"Error sending message to connection {connection_id}: {str(e)}")


def handler(event, context):
    """
    Main handler for the Agent processor Lambda.
    Processes user messages asynchronously and sends responses via WebSocket.

    Args:
        event: The event data containing connection_id, user_id, session_id, and message
        context: The Lambda context

    Returns:
        A response object
    """
    logger.info(f"Agent processor received event: {json.dumps(event)}")

    connection_id = event.get("connection_id")
    user_id = event.get("user_id", "")
    session_id = event.get("session_id", "")
    user_input = event.get("message", "")
    api_gateway_endpoint = event.get("api_gateway_endpoint", "")

    if not connection_id or not user_input or not session_id or not user_id or not api_gateway_endpoint:
        logger.error("Missing required parameters")
        return {"statusCode": 400, "body": "Missing required parameters"}

    try:
        # Send processing message to client
        send_to_connection(connection_id, {"type": "processing", "message": "Processing your request..."}, api_gateway_endpoint)

        # Get conversation history
        agent_messages = get_conversation_history(user_id, session_id)

        # Get all table information before initializing the agent
        table_information = get_all_table_information()

        # Enhance the system prompt with table information
        enhanced_system_prompt = f"{AGENT_INSTRUCTION}\n\nAVAILABLE DATABASE INFORMATION:\n{table_information}"

        # Create the agent with all the tools and conversation history
        agent = Agent(
            model=bedrock_model,
            tools=[execute_sql_query, create_downloadable_url, create_personalize_item_based_segment, check_personalize_segment_status],
            system_prompt=enhanced_system_prompt,
            messages=agent_messages,
        )

        # Get the agent's response
        agent_response = agent(user_input)

        # Save the updated messages directly from the agent
        save_conversation_history(user_id, session_id, agent.messages)

        # Filter messages for response
        conversation_history = filter_messages_for_response(agent.messages)

        # Send the response to the client
        send_to_connection(
            connection_id,
            {
                "type": "response",
                "user_id": user_id,
                "session_id": session_id,
                "response": str(agent_response),
                "conversation_history": conversation_history,
            },
            api_gateway_endpoint,
        )

        return {"statusCode": 200, "body": "Processing complete"}

    except Exception as e:
        logger.error(f"Error in agent processor: {str(e)}")

        # Send error message to client
        try:
            send_to_connection(connection_id, {"type": "error", "message": f"Error processing your request: {str(e)}"}, api_gateway_endpoint)
        except Exception as send_error:
            logger.error(f"Error sending error message: {str(send_error)}")

        return {"statusCode": 500, "body": f"Error: {str(e)}"}
