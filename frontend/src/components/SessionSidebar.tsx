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
  Button,
  IconButton
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import type { SessionInfo } from '../hooks/useSessionHistory';

interface SessionSidebarProps {
  currentSessionId: string;
  sessions: SessionInfo[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onSessionSelect: (sessionId: string) => void;
  onSessionDelete: (sessionId: string) => Promise<void>;
  onNewSession: () => void;
}

const SessionSidebar: React.FC<SessionSidebarProps> = ({
  currentSessionId,
  sessions,
  loading,
  error,
  onRefresh,
  onSessionSelect,
  onSessionDelete,
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

  const handleDeleteSession = async (sessionId: string, event: React.MouseEvent) => {
    event.stopPropagation(); // セッション選択を防ぐ
    await onSessionDelete(sessionId);
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
                  },
                  display: 'flex',
                  alignItems: 'center',
                  pr: 1,
                  '& .delete-icon': {
                    opacity: 0,
                    transition: 'opacity 0.2s'
                  },
                  '&:hover .delete-icon': {
                    opacity: 1
                  }
                }}
              >
                <ListItemText
                  primary={session.title}
                  primaryTypographyProps={{
                    noWrap: true,
                    style: { fontWeight: session.session_id === currentSessionId ? 'bold' : 'normal' }
                  }}
                  sx={{ flex: 1 }}
                />
                <IconButton
                  className="delete-icon"
                  size="small"
                  onClick={(event) => handleDeleteSession(session.session_id, event)}
                  sx={{
                    ml: 1,
                    color: 'text.secondary',
                    '&:hover': {
                      color: 'error.main'
                    }
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
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
