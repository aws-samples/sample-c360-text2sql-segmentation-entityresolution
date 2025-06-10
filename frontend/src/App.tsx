import { AppBar, Toolbar, Typography, Box, Backdrop, CircularProgress } from '@mui/material';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import ChatInterface from './components/ChatInterface';
import ErrorSnackbar from './components/ErrorSnackbar';
import { useStore } from './hooks/store';
import './App.css';

function App() {
  const { loading } = useStore();

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
                mt: 2,
                width: '100%',
                height: 'calc(100vh - 64px)',
                display: 'flex',
                justifyContent: 'center'
              }}
            >
              <Box
                sx={{
                  width: '80%',
                  maxWidth: '800px',
                  margin: '0 auto',
                  display: 'flex',
                  flexDirection: 'column'
                }}
              >
                {/* Pass userId to ChatInterface */}
                <ChatInterface userId={userId} />
              </Box>
            </Box>

            {/* Global loading indicator */}
            <Backdrop sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }} open={loading}>
              <CircularProgress color="inherit" />
            </Backdrop>

            {/* Error handling */}
            <ErrorSnackbar />
          </>
        );
      }}
    </Authenticator>
  );
}

export default App;
