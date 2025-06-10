import { CognitoJwtVerifier } from 'aws-jwt-verify';
import { APIGatewayRequestAuthorizerEvent, APIGatewayAuthorizerResult } from 'aws-lambda';

// Environment variables
const USER_POOL_ID = process.env.USER_POOL_ID!;
const USER_POOL_CLIENT_ID = process.env.USER_POOL_CLIENT_ID!;

// Create the JWT verifier
const verifier = CognitoJwtVerifier.create({
  userPoolId: USER_POOL_ID,
  clientId: USER_POOL_CLIENT_ID,
  tokenUse: 'id'
});

/**
 * Lambda authorizer for WebSocket API.
 * Validates JWT token from query parameters.
 */
export const handler = async (event: APIGatewayRequestAuthorizerEvent): Promise<APIGatewayAuthorizerResult> => {
  console.log('Authorizer event:', JSON.stringify(event, null, 2));

  try {
    // Extract token from query parameters
    const queryParams = event.queryStringParameters || {};
    const token = queryParams.token;

    if (!token) {
      console.error('No token provided');
      return generatePolicy('*', 'Deny', '*');
    }

    // Verify the JWT token
    const claims = await verifier.verify(token);
    console.log('Token verified successfully:', claims);

    // Get user ID from claims
    const userId = claims.sub;

    // Generate IAM policy with user context
    return generatePolicy(userId, 'Allow', event.methodArn, {
      userId: userId,
      scope: 'websocket'
    });
  } catch (error) {
    console.error('Error validating token:', error);
    return generatePolicy('*', 'Deny', '*');
  }
};

/**
 * Generate IAM policy for API Gateway authorizer response.
 */
function generatePolicy(
  principalId: string,
  effect: 'Allow' | 'Deny',
  resource: string,
  context?: Record<string, string>
): APIGatewayAuthorizerResult {
  const authResponse: APIGatewayAuthorizerResult = {
    principalId: principalId,
    policyDocument: {
      Version: '2012-10-17',
      Statement: [
        {
          Action: 'execute-api:Invoke',
          Effect: effect,
          Resource: resource
        }
      ]
    }
  };

  // Add context values if provided
  if (context) {
    authResponse.context = context;
  }

  return authResponse;
}
