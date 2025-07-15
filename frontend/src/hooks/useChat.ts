import { useState, useEffect, useRef } from 'react';
import useWebSocket from './useWebSocket';
import { useStore } from './store';

// Define types based on the backend structure
export type MessageContent = {
  text: string;
};

export type Message = {
  role: 'user' | 'assistant' | 'url';
  content: MessageContent[];
};

// Chat-specific WebSocket message type
interface ChatWebSocketMessage {
  type: string;
  message?: string;
  user_id?: string;
  session_id?: string;
  response?: string;
  conversation_history?: Message[];
}

const useChat = (
  userId: string,
  initialSessionId?: string,
  initialMessages: Message[] = [],
  onSessionCreated?: (sessionId: string) => void
) => {
  // 既存のセッションIDがある場合はそれを使用、新しいチャットの場合は後で生成
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);

  // initialSessionIdが変更されたらsessionIdも更新
  useEffect(() => {
    setSessionId(initialSessionId || null);
  }, [initialSessionId]);
  const [messages, setMessages] = useState<Message[]>([]);

  // initialMessagesが変更されたらmessagesも更新（常に更新）
  useEffect(() => {
    setMessages(initialMessages);
  }, [initialMessages]);
  // 最後に発言したのがユーザーかどうかでローディング状態を判断
  const isLoading = messages.length > 0 && messages[messages.length - 1].role === 'user';
  const { setShowError } = useStore();
  // Use the WebSocket store
  const { isConnected, lastMessage, sendData, connect } = useWebSocket();

  // useRefを使用して接続が既に実行されたかどうかを追跡
  const hasConnectedRef = useRef(false);

  // セッションIDが変更されたときに接続を行う
  useEffect(() => {
    if (sessionId) {
      connect(sessionId);
      hasConnectedRef.current = true;
    }
  }, [sessionId]);

  // Update messages when we get a response from WebSocket
  useEffect(() => {
    if (!lastMessage) return;

    // Process chat-related messages
    const chatMessage = lastMessage as ChatWebSocketMessage;

    // セッションIDをチェックして、現在のセッションに関連するメッセージのみを処理
    if (chatMessage.session_id && chatMessage.session_id !== sessionId) {
      return;
    }

    if (chatMessage.type === 'response') {
      if (chatMessage.conversation_history) {
        setMessages(chatMessage.conversation_history);
      }
      // 新しいセッションが作成され、接続が完了したときにコールバックを呼び出す
      if (!initialSessionId && onSessionCreated) {
        console.log('onSessionCreated is called');
        onSessionCreated(sessionId!);
      }
    } else if (chatMessage.type === 'error') {
      console.error('Chat error:', chatMessage.message);
      setShowError(true);
      // エラー時はアシスタントからのエラーメッセージを追加することでローディング状態を解除
      const errorMessage: Message = {
        role: 'assistant',
        content: [{ text: 'Sorry, there was an error processing your request. Please try again later.' }]
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    }
  }, [lastMessage, sessionId, setShowError]);

  // Function to send chat messages
  const sendMessage = async (content: string) => {
    if (!content.trim()) return;

    try {
      // セッションIDがない場合は新しく生成
      let currentSessionId = sessionId;

      const userMessage: Message = {
        role: 'user',
        content: [{ text: content }]
      };

      setMessages((prevMessages) => [...prevMessages, userMessage]);
      if (!currentSessionId) {
        currentSessionId = 'session-' + Math.random().toString(36).substring(2, 9);
        setSessionId(currentSessionId);
      }

      // まだ接続していない場合は接続
      if (!hasConnectedRef.current || !isConnected) {
        await connect(currentSessionId);
        hasConnectedRef.current = true;
      }
      // setIsLoadingは不要（messagesの変更によって自動的に判断される）

      // メッセージを送信
      const chatPayload = {
        type: 'chat',
        message: content,
        session_id: currentSessionId
      };
      await sendData(chatPayload);
    } catch (error) {
      console.error('Error sending chat message:', error);
      setShowError(true);

      // Add error message to chat
      const errorMessage: Message = {
        role: 'assistant',
        content: [{ text: 'Sorry, there was an error processing your request. Please try again later.' }]
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
      // setIsLoadingは不要（messagesの変更によって自動的に判断される）
    }
  };

  // Function to clear the chat history
  const clearChat = () => {
    setMessages([]);
  };

  return {
    userId,
    sessionId,
    messages,
    isLoading,
    isConnected,
    sendMessage,
    clearChat
  };
};

export default useChat;
