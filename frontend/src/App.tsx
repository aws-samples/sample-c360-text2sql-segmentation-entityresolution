import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import Main from './pages/Main';
import './App.css';

function App() {
  return (
    <Authenticator hideSignUp={true}>{({ signOut, user }) => <Main signOut={signOut} user={user} />}</Authenticator>
  );
}

export default App;
