import boto3
import json
import logging
import os
import re
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
        session_table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression="SET messages = :messages, last_updated = :updated",
            ExpressionAttributeValues={":messages": messages, ":updated": int(datetime.now().timestamp())},
        )
        return True

    except Exception as e:
        logger.error(f"Error saving conversation history: {str(e)}")
        return False


def set_session_connection(user_id: str, session_id: str, connection_id: str) -> bool:
    """
    セッションにWebSocket接続IDを設定する

    Args:
        user_id: ユーザーID
        session_id: セッションID
        connection_id: WebSocket接続ID

    Returns:
        設定が成功したかどうか
    """
    try:
        current_time = int(datetime.now().timestamp())

        session_table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression="SET connection_id = :conn_id, last_updated = :updated",
            ExpressionAttributeValues={":conn_id": connection_id, ":updated": current_time},
        )
        return True
    except Exception as e:
        logger.error(f"Error setting session connection: {str(e)}")
        return False


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


def remove_thinking_tags(text: str) -> str:
    """
    Remove <thinking> tags and their content from text for client display.
    This preserves the model's thinking process internally while cleaning the user-facing output.

    Args:
        text: The text that may contain <thinking> tags

    Returns:
        The text with <thinking> tags and their content removed
    """
    if not text:
        return text

    # Remove <thinking>...</thinking> blocks (including multiline)
    pattern = r"<thinking>.*?</thinking>"
    cleaned_text = re.sub(pattern, "", text, flags=re.DOTALL)

    # Remove any remaining standalone <thinking> or </thinking> tags
    cleaned_text = re.sub(r"</?thinking>", "", cleaned_text)

    # Clean up extra whitespace that might be left behind
    cleaned_text = re.sub(r"\n\s*\n\s*\n", "\n\n", cleaned_text)  # Replace multiple newlines with double newlines
    cleaned_text = cleaned_text.strip()

    return cleaned_text


def filter_messages_for_response(messages):
    """
    Filter and process messages for client response, maintaining original message order.

    This function processes the conversation messages and handles special cases:
    - Keeps regular conversation messages
    - Converts downloadable URL tool results to special URL messages
    - Filters out other tool use and tool result messages
    - Removes <thinking> tags from message content for clean client display

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
            # Clean the message content by removing <thinking> tags
            cleaned_message = {"role": message["role"], "content": []}

            for content_item in contents:
                if "text" in content_item:
                    cleaned_text = remove_thinking_tags(content_item["text"])
                    if cleaned_text:  # Only add if there's content after cleaning
                        cleaned_message["content"].append({"text": cleaned_text})
                else:
                    # Keep non-text content as is (images, etc.)
                    cleaned_message["content"].append(content_item)

            # Only add the message if it has content after cleaning
            if cleaned_message["content"]:
                filtered_messages.append(cleaned_message)
            continue

        # Check for downloadable URL tool result
        for content_item in contents:
            if "toolResult" in content_item and content_item["toolResult"].get("toolUseId") in tool_use_map:
                # Create and add special URL message
                url_text = content_item["toolResult"]["content"][0].get("text", "")
                filtered_messages.append({"role": "url", "content": [{"text": url_text}]})
                break

    return filtered_messages
