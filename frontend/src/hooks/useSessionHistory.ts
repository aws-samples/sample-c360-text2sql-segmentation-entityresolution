import { useState, useEffect } from 'react';
import useHttp from './useHttp';
import { useStore } from './store';

export interface SessionInfo {
  session_id: string;
  title: string;
  last_updated: string;
  message_count: number;
}

export interface SessionDetail {
  session_id: string;
  last_updated: string;
  messages: any[];
}

const useSessionHistory = () => {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { get } = useHttp();
  const { loading } = useStore();

  // セッション一覧を取得する関数
  const fetchSessions = async () => {
    setError(null);
    try {
      const response = await get<{ sessions: SessionInfo[] }>('/sessions');
      console.log('fetched sessions..');
      console.log(response);
      setSessions(response.sessions || []);
    } catch (err) {
      console.error('セッション履歴の取得に失敗しました:', err);
      setError('セッション履歴の取得に失敗しました');
    }
  };

  // 特定のセッションの詳細を取得する関数
  const fetchSessionDetail = async (sessionId: string): Promise<SessionDetail | null> => {
    setError(null);
    try {
      const response = await get<SessionDetail>(`/sessions/${sessionId}`);
      return response;
    } catch (err) {
      console.error(`セッション ${sessionId} の詳細取得に失敗しました:`, err);
      setError(`セッション ${sessionId} の詳細取得に失敗しました`);
      return null;
    }
  };

  // コンポーネントのマウント時にセッション一覧を取得
  useEffect(() => {
    fetchSessions();
  }, []);

  return {
    sessions,
    loading,
    error,
    fetchSessions,
    fetchSessionDetail
  };
};

export default useSessionHistory;
