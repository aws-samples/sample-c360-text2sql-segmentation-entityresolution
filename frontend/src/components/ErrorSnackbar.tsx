import { Alert, Snackbar } from '@mui/material';
import { useStore } from '../hooks/store';

const ErrorSnackbar = () => {
  const { showError, setShowError } = useStore();

  const handleClose = () => {
    setShowError(false);
  };

  return (
    <Snackbar open={showError} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} onClick={handleClose}>
      <Alert severity="error" sx={{ width: '100%', cursor: 'pointer' }}>
        エラーが発生しました。
      </Alert>
    </Snackbar>
  );
};

export default ErrorSnackbar;
