import boto3
import json
import logging
import os
from datetime import datetime
from sessionutils import (
    get_conversation_history,
    filter_messages_for_response,
    update_session_connection,
    find_sessions_by_connection_id,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
lambda_client = boto3.client("lambda")

# Environment variables
AGENT_PROCESSOR_FUNCTION_NAME = os.environ["AGENT_PROCESSOR_FUNCTION_NAME"]


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

    # Handle system route types
    if route_key == "$connect":
        return handle_connect(event, connection_id)
    elif route_key == "$disconnect":
        return handle_disconnect(connection_id)
    else:
        # Handle all messages based on type in the body
        try:
            body = json.loads(event.get("body", "{}"))
            message_type = body.get("type")

            if message_type == "chat":
                return handle_chat(event, connection_id)
            elif message_type == "ping":
                return handle_ping(connection_id, event)
            elif message_type == "fetch_history":
                return handle_fetch_history(event, connection_id)
            else:
                logger.warning(f"Unknown message type: {message_type}")
        except Exception as e:
            logger.error(f"Error parsing message body: {str(e)}")

        return handle_default(connection_id)


def handle_connect(event, connection_id):
    """
    Handle WebSocket connection event.
    接続時にsession_idとconnection_idのマッピングを保存する。
    """
    try:
        # Get user ID from authorizer context
        request_context = event["requestContext"]
        authorizer = request_context["authorizer"]
        user_id = authorizer["userId"]

        # クエリパラメータからsession_idを取得（フロントエンドから提供される）
        query_params = event.get("queryStringParameters", {}) or {}
        session_id = query_params.get("session_id")

        logger.info(f"WebSocket connected: connection_id={connection_id}, user_id={user_id}, session_id={session_id}")

        # session_idが提供された場合、セッション接続情報を更新
        if session_id:
            update_session_connection(user_id, session_id, connection_id, "connected")
            logger.info(f"Updated session mapping: session_id={session_id}, connection_id={connection_id}")

        return {"statusCode": 200, "body": "Connected"}
    except Exception as e:
        logger.error(f"Error in handle_connect: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}


def handle_disconnect(connection_id):
    """
    Handle WebSocket disconnect event.
    切断時にConversationSessionTableのconnection_statusを更新する。
    """
    try:
        logger.info(f"WebSocket disconnected: connection_id={connection_id}")

        # このconnection_idを持つセッションを検索
        sessions = find_sessions_by_connection_id(connection_id)

        # 見つかったセッションのconnection_statusを更新
        for session in sessions:
            user_id = session.get("user_id")
            session_id = session.get("session_id")

            if user_id and session_id:
                update_session_connection(user_id, session_id, connection_id, "disconnected")
                logger.info(f"Updated session status to disconnected: user_id={user_id}, session_id={session_id}")

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


def handle_fetch_history(event, connection_id):
    """
    会話履歴を取得するためのハンドラー
    """
    try:
        # メッセージボディを解析
        body = json.loads(event.get("body", "{}"))
        request_context = event["requestContext"]
        authorizer = request_context["authorizer"]
        user_id = authorizer["userId"]
        session_id = body.get("session_id")

        if not session_id:
            send_to_connection(connection_id, {"type": "error", "message": "No session_id provided"})
            return {"statusCode": 400, "body": "No session_id provided"}

        logger.info(f"Fetching conversation history for user_id={user_id}, session_id={session_id}")

        # 会話履歴を取得
        conversation_history = get_conversation_history(user_id, session_id)

        # フィルタリングされた会話履歴を取得
        filtered_history = filter_messages_for_response(conversation_history)

        api_gateway_endpoint = get_api_endpoint(event)

        # 会話履歴を送信
        send_to_connection(
            connection_id,
            {"type": "history", "user_id": user_id, "session_id": session_id, "conversation_history": filtered_history},
            api_gateway_endpoint,
        )

        return {"statusCode": 200, "body": "History fetched"}
    except Exception as e:
        logger.error(f"Error in handle_fetch_history: {str(e)}")
        api_gateway_endpoint = get_api_endpoint(event)
        send_to_connection(connection_id, {"type": "error", "message": f"Error fetching history: {str(e)}"}, api_gateway_endpoint)
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


# filter_messages_for_response is now imported from sessionutils
