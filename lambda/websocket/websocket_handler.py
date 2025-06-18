import boto3
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

# Environment variables
SESSION_TABLE = os.environ["SESSION_TABLE"]
AGENT_PROCESSOR_FUNCTION_NAME = os.environ["AGENT_PROCESSOR_FUNCTION_NAME"]

# DynamoDB tables
session_table = dynamodb.Table(SESSION_TABLE)


def handler(event, context):
    """
    Main handler for WebSocket API events.
    Handles connect, disconnect, and message events.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")

    if not connection_id:
        return {"statusCode": 400, "body": "Missing connectionId"}

    # Handle different route types
    if route_key == "$connect":
        return handle_connect(event, connection_id)
    elif route_key == "$disconnect":
        return handle_disconnect(connection_id)
    elif route_key == "chat":
        return handle_chat(event, connection_id)
    else:
        # Check if this is a ping message
        try:
            body = json.loads(event.get("body", "{}"))
            if body.get("type") == "ping":
                return handle_ping(connection_id, event)
        except Exception as e:
            logger.error(f"Error parsing message body: {str(e)}")

        return handle_default(connection_id)


def handle_connect(event, connection_id):
    """
    Handle WebSocket connection event.
    """
    try:
        # Get user ID from authorizer context
        request_context = event["requestContext"]
        authorizer = request_context["authorizer"]
        user_id = authorizer["userId"]

        logger.info(f"WebSocket connected: connection_id={connection_id}, user_id={user_id}")

        return {"statusCode": 200, "body": "Connected"}
    except Exception as e:
        logger.error(f"Error in handle_connect: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def handle_disconnect(connection_id):
    """
    Handle WebSocket disconnect event.
    """
    try:
        logger.info(f"WebSocket disconnected: connection_id={connection_id}")
        return {"statusCode": 200, "body": "Disconnected"}
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def get_api_endpoint(event):
    # Get API Gateway endpoint for WebSocket communication
    domain_name = event.get("requestContext", {}).get("domainName")
    stage = event.get("requestContext", {}).get("stage")
    return f"https://{domain_name}/{stage}"


def handle_chat(event, connection_id):
    """
    Handle chat messages.
    Invoke the agent processor Lambda asynchronously.
    """
    try:
        # Parse the message body
        body = json.loads(event.get("body", "{}"))
        user_input = body.get("message", "")
        request_context = event["requestContext"]
        authorizer = request_context["authorizer"]
        user_id = authorizer["userId"]
        session_id = body["session_id"]

        if not user_input:
            send_to_connection(connection_id, {"type": "error", "message": "No message provided"})
            return {"statusCode": 400, "body": "No message provided"}

        # Send acknowledgment to the client
        api_gateway_endpoint = get_api_endpoint(event)
        send_to_connection(
            connection_id,
            {"type": "ack", "message": "Message received, processing...", "user_id": user_id, "session_id": session_id},
            api_gateway_endpoint,
        )

        # Invoke the agent processor Lambda asynchronously
        lambda_client.invoke(
            FunctionName=AGENT_PROCESSOR_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "connection_id": connection_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": user_input,
                    "api_gateway_endpoint": api_gateway_endpoint,
                }
            ),
        )

        return {"statusCode": 200, "body": "Processing message"}
    except Exception as e:
        logger.error(f"Error in handle_chat: {str(e)}")
        send_to_connection(connection_id, {"type": "error", "message": f"Error processing message: {str(e)}"}, api_gateway_endpoint)
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def handle_ping(connection_id, event):
    """
    Handle ping messages for keeping the WebSocket connection alive.
    Responds with a pong message.
    """
    try:
        logger.info(f"Received ping from connection_id={connection_id}")

        # Get API Gateway endpoint
        api_gateway_endpoint = get_api_endpoint(event)

        # Send pong response
        send_to_connection(
            connection_id, {"type": "pong", "timestamp": event.get("requestContext", {}).get("requestTimeEpoch")}, api_gateway_endpoint
        )

        return {"statusCode": 200, "body": "Pong sent"}
    except Exception as e:
        logger.error(f"Error in handle_ping: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def handle_default(connection_id):
    """
    Handle default route (unknown route key).
    """
    try:
        logger.warning(f"Unknown route for connection_id={connection_id}")
        return {"statusCode": 400, "body": "Unknown route"}
    except Exception as e:
        logger.error(f"Error in handle_default: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def send_to_connection(connection_id, data, api_gateway_endpoint):
    """
    Send a message to a WebSocket connection.

    Args:
        connection_id: The WebSocket connection ID
        data: The data to send (will be converted to JSON)
        api_gateway_endpoint: The API Gateway endpoint URL
    """
    if not api_gateway_endpoint:
        logger.error(f"No API Gateway endpoint provided for connection {connection_id}")
        return

    gateway_api = boto3.client("apigatewaymanagementapi", endpoint_url=api_gateway_endpoint)

    try:
        gateway_api.post_to_connection(ConnectionId=connection_id, Data=json.dumps(data).encode("utf-8"))
        logger.info(f"Message sent to connection {connection_id}: {json.dumps(data)}")
    except Exception as e:
        logger.error(f"Error sending message to connection {connection_id}: {str(e)}")


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
