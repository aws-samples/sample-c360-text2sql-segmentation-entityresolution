import { useState, useRef, useEffect } from 'react';
import {
  Typography,
  Box,
  Paper,
  TextField,
  Button,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Chip
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import useChat from '../hooks/useChat';
import type { Message } from '../hooks/useChat';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';

interface ChatInterfaceProps {
  userId: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ userId }) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Pass userId to useChat hook
  const { messages, isLoading, isConnected, sendMessage } = useChat(userId);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = () => {
    if (inputValue.trim() && isConnected) {
      sendMessage(inputValue);
      setInputValue('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Helper function to get message content as string
  const getMessageContent = (message: Message): string => {
    if (!message.content || !Array.isArray(message.content) || message.content.length === 0) {
      return '';
    }

    // Extract text from the first content item
    return message.content[0]?.text || '';
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
        <Chip
          icon={isConnected ? <WifiIcon /> : <WifiOffIcon />}
          label={isConnected ? 'Connected' : 'Disconnected'}
          color={isConnected ? 'success' : 'error'}
          size="small"
        />
      </Box>
      <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
        <Paper elevation={3} sx={{ p: 2, overflow: 'auto' }}>
          <List>
            {messages.map((message: Message, index: number) => (
              <ListItem
                key={index}
                sx={{
                  display: 'flex',
                  justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                  mb: 1
                }}
              >
                <Paper
                  elevation={1}
                  sx={{
                    p: 2,
                    maxWidth: '80%',
                    bgcolor: message.role === 'user' ? '#e3f2fd' : message.role === 'url' ? '#e8f5e9' : '#f5f5f5',
                    borderRadius: 2
                  }}
                >
                  {message.role === 'user' ? (
                    <ListItemText primary={getMessageContent(message)} secondary="You" />
                  ) : message.role === 'url' ? (
                    <Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                        Download Link
                      </Typography>
                      <Box
                        sx={{
                          '& a': {
                            color: 'primary.main',
                            textDecoration: 'none'
                          }
                        }}
                      >
                        <Button
                          variant="contained"
                          color="inherit"
                          size="small"
                          href={getMessageContent(message)}
                          target="_blank"
                          sx={{ mt: 1 }}
                        >
                          Download Results
                        </Button>
                      </Box>
                    </Box>
                  ) : (
                    <Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                        Assistant
                      </Typography>
                      <Box
                        sx={{
                          '& pre': {
                            backgroundColor: '#f5f5f5',
                            p: 1.5,
                            borderRadius: 1,
                            overflowX: 'auto'
                          },
                          '& code': {
                            fontFamily: 'monospace',
                            fontSize: '0.875rem'
                          },
                          '& p': {
                            my: 1
                          },
                          '& a': {
                            color: 'primary.main',
                            textDecoration: 'none'
                          },
                          '& ul, & ol': {
                            pl: 2
                          },
                          '& table': {
                            borderCollapse: 'collapse',
                            width: '100%'
                          },
                          '& th, & td': {
                            border: '1px solid #ddd',
                            p: 1
                          }
                        }}
                      >
                        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{getMessageContent(message)}</ReactMarkdown>
                      </Box>
                    </Box>
                  )}
                </Paper>
              </ListItem>
            ))}
            {isLoading && (
              <ListItem sx={{ display: 'flex', justifyContent: 'flex-start', mb: 1 }}>
                <CircularProgress size={20} sx={{ mr: 2 }} />
                <Typography variant="body2" color="text.secondary">
                  Assistant is thinking...
                </Typography>
              </ListItem>
            )}
            <div ref={messagesEndRef} />
          </List>
        </Paper>
      </Box>
      <Box sx={{ p: 2, position: 'sticky', bottom: 0, bgcolor: 'background.default' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Type your message here..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading || !isConnected}
            multiline
            maxRows={4}
            sx={{ mr: 1 }}
          />
          <Button
            variant="contained"
            color="primary"
            endIcon={<SendIcon />}
            onClick={handleSendMessage}
            disabled={isLoading || !inputValue.trim() || !isConnected}
          >
            Send
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default ChatInterface;
