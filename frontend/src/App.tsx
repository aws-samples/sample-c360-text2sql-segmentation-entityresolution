import { AppBar, Toolbar, Typography, Box, Backdrop, CircularProgress } from '@mui/material';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import ChatInterface from './components/ChatInterface';
import SessionSidebar from './components/SessionSidebar';
import ErrorSnackbar from './components/ErrorSnackbar';
import { useStore } from './hooks/store';
import useSessionHistory from './hooks/useSessionHistory';
import { useState, useEffect } from 'react';
import './App.css';

function App() {
  const { loading } = useStore();
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(undefined);
  const { sessions, loading: sessionsLoading, error, fetchSessions, fetchSessionDetail } = useSessionHistory();
  const [currentSessionMessages, setCurrentSessionMessages] = useState<any[]>([]);

  // セッションIDが変更されたら、そのセッションの詳細情報を取得
  useEffect(() => {
    const loadSessionDetails = async () => {
      if (currentSessionId) {
        const sessionDetail = await fetchSessionDetail(currentSessionId);
        if (sessionDetail && sessionDetail.messages) {
          setCurrentSessionMessages(sessionDetail.messages);
        } else {
          setCurrentSessionMessages([]);
        }
      } else {
        setCurrentSessionMessages([]);
      }
    };

    loadSessionDetails();
  }, [currentSessionId]);

  const onNewSessionCreated = (sessionId) => {
    fetchSessions();
    setCurrentSessionId(sessionId);
  };
  return (
    <Authenticator hideSignUp={true}>
      {({ signOut, user }) => {
        // Get userId from Amplify user object, or use a fallback
        const userId = user?.username || 'anonymous-user';

        return (
          <>
            <AppBar position="static">
              <Toolbar sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h6">C360 AI Chat Assistant</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Typography variant="body1" sx={{ mr: 2 }}>
                    {user?.username}
                  </Typography>
                  <Typography variant="button" component="span" onClick={signOut} sx={{ cursor: 'pointer' }}>
                    Sign Out
                  </Typography>
                </Box>
              </Toolbar>
            </AppBar>
            <Box
              sx={{
                width: '100%',
                height: 'calc(100vh - 64px)',
                display: 'flex'
              }}
            >
              {/* セッション履歴サイドバー */}
              <SessionSidebar
                currentSessionId={currentSessionId || ''}
                sessions={sessions}
                loading={sessionsLoading}
                error={error}
                onRefresh={fetchSessions}
                onSessionSelect={setCurrentSessionId}
                onNewSession={() => {
                  // 新しいチャットボタンがクリックされたときに、currentSessionIdをundefinedに設定
                  setCurrentSessionId(undefined);
                }}
              />

              {/* チャットインターフェース */}
              <Box
                sx={{
                  flexGrow: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  height: '100%',
                  overflow: 'hidden'
                }}
              >
                <ChatInterface
                  userId={userId}
                  sessionId={currentSessionId}
                  initialMessages={currentSessionMessages}
                  onSessionCreated={(newSessionId) => onNewSessionCreated(newSessionId)} // 新しいセッションが作成されたらセッションリストを更新
                />
              </Box>
            </Box>

            {/* Error handling */}
            <ErrorSnackbar />
          </>
        );
      }}
    </Authenticator>
  );
}

export default App;
