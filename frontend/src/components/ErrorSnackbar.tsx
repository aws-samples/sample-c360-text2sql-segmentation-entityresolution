import { Alert, Snackbar } from '@mui/material';
import { useStore } from '../hooks/store';

const ErrorSnackbar = () => {
  const { showError, setShowError } = useStore();

  const handleClose = () => {
    setShowError(false);
  };

  return (
    <Snackbar
      open={showError}
      autoHideDuration={6000}
      onClose={handleClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
    >
      <Alert onClose={handleClose} severity="error" sx={{ width: '100%' }}>
        An error occurred. Please try again later.
      </Alert>
    </Snackbar>
  );
};

export default ErrorSnackbar;
