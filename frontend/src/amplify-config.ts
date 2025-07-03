import { Amplify } from 'aws-amplify';

export const configureAmplify = () => {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: String(import.meta.env.VITE_APP_USER_POOL_ID),
        userPoolClientId: String(import.meta.env.VITE_APP_USER_POOL_WEB_CLIENT_ID)
      }
    }
  });
};
