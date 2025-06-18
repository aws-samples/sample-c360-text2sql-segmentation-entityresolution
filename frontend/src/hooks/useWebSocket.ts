import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchAuthSession } from 'aws-amplify/auth';
import { useStore } from './store';
import jsonParseSafe from 'json-parse-safe';

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

const useWebSocket = () => {
  const { setShowError } = useStore();
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Get WebSocket URL from environment variables
  const wsUrl = import.meta.env.VITE_APP_WEBSOCKET_URL;

  // Start heartbeat to keep connection alive
  const startHeartbeat = useCallback(() => {
    // Clear any existing heartbeat interval
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    
    // Set up new heartbeat interval - 3 minutes (180000 ms)
    heartbeatIntervalRef.current = setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        console.log('Sending heartbeat ping to keep connection alive');
        socketRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 180000); // 3 minutes
    
    return () => {
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
    };
  }, []);

  // Connect to WebSocket with authentication and wait for connection to establish
  const connect = useCallback(async () => {
    try {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected');
        return;
      }

      // Get authentication session
      const session = await fetchAuthSession();
      const idToken = session.tokens?.idToken?.toString();

      if (!idToken) {
        console.error('No ID token available in session');
        setShowError(true);
        return;
      }

      // Create WebSocket connection with token for authentication
      const url = `${wsUrl}?token=${encodeURIComponent(idToken)}`;
      socketRef.current = new WebSocket(url);

      socketRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        
        // Start heartbeat when connection is established
        startHeartbeat();
      };

      socketRef.current.onmessage = (event) => {
        try {
          const parsed = jsonParseSafe(event.data);
          if ('value' in parsed) {
            const data: WebSocketMessage = parsed.value;
            console.log('WebSocket message received:', data);
            setLastMessage(data);
          } else {
            console.error('Invalid WebSocket message format:', event.data);
            setShowError(true);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      socketRef.current.onclose = (event) => {
        console.log(`WebSocket disconnected: code=${event.code}, reason=${event.reason}, wasClean=${event.wasClean}`, event);
        setIsConnected(false);

        // Stop heartbeat on disconnect
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current);
          heartbeatIntervalRef.current = null;
        }

        // Attempt to reconnect after a delay
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }

        // reconnectTimeoutRef.current = setTimeout(() => {
        //   console.log('Attempting to reconnect WebSocket...');
        //   connect();
        // }, 3000);
      };

      socketRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setShowError(true);
      };

      // Wait for connection to establish
      await new Promise<void>((resolve, reject) => {
        const checkConnection = () => {
          if (!socketRef.current) {
            reject(new Error('WebSocket connection failed'));
            return;
          }

          if (socketRef.current.readyState === WebSocket.OPEN) {
            resolve();
          } else if (
            socketRef.current.readyState === WebSocket.CLOSED ||
            socketRef.current.readyState === WebSocket.CLOSING
          ) {
            reject(new Error('WebSocket connection closed'));
          } else {
            setTimeout(checkConnection, 100);
          }
        };
        checkConnection();
      });
    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
      setShowError(true);
      throw error;
    }
  }, [setShowError, wsUrl, startHeartbeat]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    // Stop heartbeat
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const sendData = async (payload: any) => {
    try {
      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        console.log('WebSocket not connected, attempting to connect...');
        await connect();
      }

      console.log('Sending data via WebSocket:', payload);
      socketRef.current?.send(JSON.stringify(payload));
    } catch (error) {
      console.error('Error sending data:', error);
      setShowError(true);
      throw error;
    }
  };

  // Connect on component mount, disconnect on unmount
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    sendData,
    connect,
    disconnect
  };
};

export default useWebSocket;
