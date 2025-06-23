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

const useChat = (userId: string) => {
  // Initialize with a session_id
  const [sessionId] = useState<string>('session-' + Math.random().toString(36).substring(2, 9));
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const { setShowError } = useStore();

  // Use the WebSocket store
  const { isConnected, lastMessage, sendData, connect, disconnect } = useWebSocket();

  // 接続時に会話履歴を取得する
  const fetchHistory = (sessionId: string) => {
    console.log('Fetching conversation history for session:', sessionId);
    sendData({
      type: 'fetch_history',
      session_id: sessionId
    });
  };

  // useRefを使用して接続が既に実行されたかどうかを追跡
  const hasConnectedRef = useRef(false);

  useEffect(() => {
    // 初回のみ接続を実行
    if (!hasConnectedRef.current && !isConnected) {
      console.log('Initial connection attempt');
      connect(sessionId);
      hasConnectedRef.current = true;
    }
  }, []);

  // WebSocket接続時にセッションIDを渡す
  useEffect(() => {
    // 接続状態が変わったときに会話履歴を取得
    if (isConnected) {
      fetchHistory(sessionId);
    }
  }, [isConnected]);

  // Update messages when we get a response from WebSocket
  useEffect(() => {
    if (!lastMessage) return;

    // Process chat-related messages
    const chatMessage = lastMessage as ChatWebSocketMessage;

    if (chatMessage.type === 'response') {
      if (chatMessage.conversation_history) {
        setMessages(chatMessage.conversation_history);
      }
      setIsLoading(false);
    } else if (chatMessage.type === 'error') {
      console.error('Chat error:', chatMessage.message);
      setShowError(true);
      setIsLoading(false);
    } else if (chatMessage.type === 'history') {
      if (chatMessage.conversation_history) {
        setMessages(chatMessage.conversation_history);
      }
      setIsLoading(false);
    }
  }, [lastMessage, setShowError]);

  // Function to send chat messages
  const sendMessage = async (content: string) => {
    if (!content.trim()) return;

    // Add user message to local state immediately for better UX
    const userMessage: Message = {
      role: 'user',
      content: [{ text: content }]
    };

    console.log('### sessionId:' + sessionId);
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setIsLoading(true);

    try {
      const chatPayload = {
        type: 'chat',
        message: content,
        session_id: sessionId
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
      setIsLoading(false);
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
