import boto3
import os
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import (
    APIGatewayRestResolver,
    Response,
    CORSConfig,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler.exceptions import InternalServerError
from sessionutils import filter_messages_for_response


logger = Logger()


ALLOW_ORIGIN = os.environ["ALLOW_ORIGIN"]
SESSION_TABLE = os.environ["SESSION_TABLE"]
dynamodb = boto3.resource("dynamodb")
session_table = dynamodb.Table(SESSION_TABLE)

# APIGatewayRestResolverの初期化
app = APIGatewayRestResolver(cors=CORSConfig(allow_origin=ALLOW_ORIGIN))


@app.get("/sessions")
def get_user_sessions():
    """
    ユーザーのすべてのセッション履歴を取得するエンドポイント
    """
    try:
        # リクエストからユーザーIDを取得
        user_id = app.current_event.request_context.authorizer.get("claims", {}).get("sub")

        if not user_id:
            return {"statusCode": 400, "body": "User ID not found in token"}

        # ユーザーのセッションをDynamoDBから取得
        response = session_table.query(KeyConditionExpression="user_id = :user_id", ExpressionAttributeValues={":user_id": user_id})

        # セッション情報を整形
        sessions = []
        for item in response.get("Items", []):
            # 最初のメッセージがあれば、それをセッションのタイトルとして使用
            title = "New Chat"
            messages = item.get("messages", [])
            if messages and len(messages) > 0:
                # ユーザーの最初のメッセージを探す
                for msg in messages:
                    if msg.get("role") == "user" and msg.get("content"):
                        content = msg.get("content", [])
                        if content and len(content) > 0 and "text" in content[0]:
                            # 最初の50文字をタイトルとして使用
                            title = content[0]["text"][:50]
                            if len(content[0]["text"]) > 50:
                                title += "..."
                            break

            # セッション情報を追加
            sessions.append(
                {"session_id": item.get("session_id"), "title": title, "last_updated": item.get("last_updated"), "message_count": len(messages)}
            )

        # 最終更新日時で降順ソート（None値を適切に処理）
        sessions.sort(key=lambda x: (x.get("last_updated") or ""), reverse=True)

        return Response(status_code=200, content_type="application/json", body={"sessions": sessions})

    except Exception as e:
        logger.exception("Error retrieving user sessions")
        raise InternalServerError("Error retrieving user sessions")


@app.get("/sessions/<session_id>")
def get_session_details(session_id):
    """
    特定のセッションの詳細を取得するエンドポイント
    """
    try:
        # リクエストからユーザーIDを取得
        user_id = app.current_event.request_context.authorizer.get("claims", {}).get("sub")

        response = session_table.get_item(Key={"user_id": user_id, "session_id": session_id})
        if "Item" in response:
            conversation_history = response["Item"].get("messages", [])
            last_updated = response["Item"].get("last_updated")
        else:
            conversation_history = []
            last_updated = None

        # sessionutils.pyのfilter_messages_for_responseを使用してメッセージをフィルタリング
        filtered_messages = filter_messages_for_response(conversation_history)

        # 必要な情報のみを返す
        return Response(
            status_code=200,
            content_type="application/json",
            body={
                "session_id": session_id,
                "last_updated": last_updated,
                "messages": filtered_messages,
            },
        )

    except Exception as e:
        logger.exception(f"Error retrieving session details for session_id: {session_id}")
        raise InternalServerError("Error retrieving session details")


@app.delete("/sessions/<session_id>")
def delete_session(session_id):
    """
    特定のセッションを削除するエンドポイント
    """
    try:
        # リクエストからユーザーIDを取得
        user_id = app.current_event.request_context.authorizer.get("claims", {}).get("sub")

        if not user_id:
            return Response(status_code=400, content_type="application/json", body={"error": "User ID not found in token"})

        # セッションを削除
        session_table.delete_item(Key={"user_id": user_id, "session_id": session_id})

        logger.info(f"Session {session_id} deleted successfully for user {user_id}")

        return Response(
            status_code=200, content_type="application/json", body={"message": "Session deleted successfully", "session_id": session_id}
        )

    except Exception as e:
        logger.exception(f"Error deleting session {session_id}")
        raise InternalServerError("Error deleting session")


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context: LambdaContext):
    """
    Lambda関数のメインハンドラー
    """
    return app.resolve(event, context)
