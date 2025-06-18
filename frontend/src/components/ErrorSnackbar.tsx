import { Alert, Snackbar } from '@mui/material';
import { useStore } from '../hooks/store';

const ErrorSnackbar = () => {
  const { showError } = useStore();

  return (
    <Snackbar open={showError} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
      <Alert severity="error" sx={{ width: '100%' }}>
        エラーが発生しました。ブラウザリロードしてください
      </Alert>
    </Snackbar>
  );
};

export default ErrorSnackbar;
