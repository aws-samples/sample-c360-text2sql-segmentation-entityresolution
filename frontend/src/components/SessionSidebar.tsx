import React from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
  Divider,
  CircularProgress,
  Button
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import type { SessionInfo } from '../hooks/useSessionHistory';

interface SessionSidebarProps {
  currentSessionId: string;
  sessions: SessionInfo[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSessionSelect: (sessionId: string) => void;
  onNewSession: () => void;
}

const SessionSidebar: React.FC<SessionSidebarProps> = ({
  currentSessionId,
  sessions,
  loading,
  error,
  onRefresh,
  onSessionSelect,
  onNewSession
}) => {
  const handleRefresh = () => {
    onRefresh();
  };

  const handleSessionClick = (sessionId: string) => {
    onSessionSelect(sessionId);
  };

  const handleNewSession = () => {
    onNewSession();
  };

  const sidebarContent = (
    <>
      <Divider />
      <Box sx={{ p: 1 }}>
        <Button
          variant="contained"
          color="primary"
          fullWidth
          startIcon={<AddIcon />}
          onClick={handleNewSession}
          sx={{ mb: 2 }}
        >
          新しいチャット
        </Button>
      </Box>
      <Divider />
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress size={24} />
        </Box>
      ) : error ? (
        <Box sx={{ p: 2 }}>
          <Typography color="error">{error}</Typography>
          <Button onClick={handleRefresh} sx={{ mt: 1 }}>
            再読み込み
          </Button>
        </Box>
      ) : sessions.length === 0 ? (
        <Box sx={{ p: 2 }}>
          <Typography variant="body2" color="text.secondary">
            チャット履歴がありません
          </Typography>
        </Box>
      ) : (
        <List sx={{ overflow: 'auto' }}>
          {sessions.map((session: SessionInfo) => (
            <ListItem key={session.session_id} disablePadding>
              <ListItemButton
                selected={session.session_id === currentSessionId}
                onClick={() => handleSessionClick(session.session_id)}
                sx={{
                  '&.Mui-selected': {
                    backgroundColor: 'rgba(25, 118, 210, 0.08)'
                  }
                }}
              >
                <ListItemText
                  primary={session.title}
                  primaryTypographyProps={{
                    noWrap: true,
                    style: { fontWeight: session.session_id === currentSessionId ? 'bold' : 'normal' }
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      )}
    </>
  );

  return (
    <Box
      sx={{
        width: 280,
        flexShrink: 0,
        borderRight: 1,
        borderColor: 'divider',
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {sidebarContent}
    </Box>
  );
};

export default SessionSidebar;
