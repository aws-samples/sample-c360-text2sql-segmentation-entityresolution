import boto3
import json
import logging
import os
from datetime import datetime
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB clients
dynamodb = boto3.resource("dynamodb")

# Environment variables
SESSION_TABLE = os.environ["SESSION_TABLE"]

# DynamoDB tables
session_table = dynamodb.Table(SESSION_TABLE)


def get_conversation_history(user_id: str, session_id: str) -> list:
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


def save_conversation_history(user_id: str, session_id: str, messages: list) -> bool:
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
            Item={"user_id": user_id, "session_id": session_id, "messages": messages, "last_updated": int(datetime.now().timestamp())}
        )
        return True

    except Exception as e:
        logger.error(f"Error saving conversation history: {str(e)}")
        return False


def update_session_connection(user_id: str, session_id: str, connection_id: str, status: str = "connected") -> bool:
    """
    セッションの接続情報を更新する

    Args:
        user_id: ユーザーID
        session_id: セッションID
        connection_id: 接続ID
        status: 接続ステータス ("connected" または "disconnected")

    Returns:
        更新が成功したかどうか
    """
    try:
        current_time = int(datetime.now().timestamp())
        update_expr = "SET connection_id = :conn_id, connection_status = :status, last_updated = :updated"
        expr_attr_values = {":conn_id": connection_id, ":status": status, ":updated": current_time}

        if status == "connected":
            update_expr += ", last_connected = :time"
            expr_attr_values[":time"] = current_time
        else:
            update_expr += ", last_disconnected = :time"
            expr_attr_values[":time"] = current_time

        session_table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_values,
        )
        return True
    except Exception as e:
        logger.error(f"Error updating session connection: {str(e)}")
        return False


def find_sessions_by_connection_id(connection_id: str) -> list:
    """
    指定された接続IDに関連付けられたセッションを検索する

    Args:
        connection_id: 接続ID

    Returns:
        セッションのリスト
    """
    try:
        response = session_table.scan(FilterExpression=Attr("connection_id").eq(connection_id))

        if "Items" in response and response["Items"]:
            return response["Items"]
        else:
            return []
    except Exception as e:
        logger.error(f"Error finding sessions by connection_id: {str(e)}")
        return []


def get_active_connection_id(user_id: str, session_id: str) -> str:
    """
    指定されたuser_idとsession_idに関連付けられた最新のconnection_idを取得する

    Args:
        user_id: ユーザーID
        session_id: セッションID

    Returns:
        最新のconnection_id、または見つからない場合はNone
    """
    try:
        response = session_table.get_item(Key={"user_id": user_id, "session_id": session_id})

        if "Item" in response and "connection_id" in response["Item"]:
            return response["Item"]["connection_id"]

        return None
    except Exception as e:
        logger.error(f"Error getting active connection_id: {str(e)}")
        return None


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
