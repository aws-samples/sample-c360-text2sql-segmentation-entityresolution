import { Amplify } from 'aws-amplify';

export const configureAmplify = () => {
  Amplify.configure({
    Auth: {
      Cognito: {
        region: import.meta.env.VITE_APP_REGION,
        userPoolId: import.meta.env.VITE_APP_USER_POOL_ID,
        userPoolClientId: import.meta.env.VITE_APP_USER_POOL_WEB_CLIENT_ID,
        identityPoolId: import.meta.env.VITE_APP_ID_POOL_ID,
      }
    }
  });
};
