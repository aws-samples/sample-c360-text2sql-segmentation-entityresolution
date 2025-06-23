import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as apigatewayv2_integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as apigatewayv2_authorizers from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import * as nodejs from 'aws-cdk-lib/aws-lambda-nodejs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { Cognito } from './cognito';
import { DataStorage } from './data-storage';
import { PersonalizeSegmentWorkflow } from './personalize-segment-workflow';
import { PersonalizeStore } from './solution-version-store';

interface WebBackendProps {
  dataStorage: DataStorage;
  personalizeSegmentWorkflow: PersonalizeSegmentWorkflow;
  personalizeStore: PersonalizeStore;
}

export class WebBackend extends Construct {
  public readonly agentProcessor: PythonFunction;
  public readonly websocketHandler: PythonFunction;
  public readonly sessionTable: dynamodb.Table;
  public readonly cognito: Cognito;
  public readonly webSocketApi: apigatewayv2.WebSocketApi;
  public readonly webSocketStage: apigatewayv2.WebSocketStage;

  constructor(scope: Construct, id: string, props: WebBackendProps) {
    super(scope, id);

    // DynamoDB table for storing conversation sessions
    this.sessionTable = new dynamodb.Table(this, 'ConversationSessionTable', {
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'session_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY // For development only, use RETAIN for production
    });

    // Agent processor Lambda function (for async processing)
    this.agentProcessor = new PythonFunction(this, 'AgentProcessor', {
      entry: 'lambda/websocket',
      runtime: lambda.Runtime.PYTHON_3_13,
      index: 'agent_processor.py',
      handler: 'handler',
      timeout: cdk.Duration.minutes(15),
      environment: {
        SESSION_TABLE: this.sessionTable.tableName,
        DDB_SESSION_TABLE: this.sessionTable.tableName,
        ATHENA_DATABASE: props.dataStorage.glueDatabase.databaseName,
        ATHENA_OUTPUT_LOCATION: `s3://${props.dataStorage.athenaResultBucket.bucketName}/athena-results/`,
        ATHENA_WORKGROUP: 'primary',
        SEGMENT_STATE_MACHINE_ARN: props.personalizeSegmentWorkflow.stateMachine.stateMachineArn,
        SOLUTION_VERSION_TABLE: props.personalizeStore.personalizeTable.tableName
      },
      memorySize: 512
    });
    // WebSocket handler Lambda function
    this.websocketHandler = new PythonFunction(this, 'WebSocketHandler', {
      entry: 'lambda/websocket',
      runtime: lambda.Runtime.PYTHON_3_13,
      index: 'websocket_handler.py',
      handler: 'handler',
      timeout: cdk.Duration.seconds(60),
      environment: {
        SESSION_TABLE: this.sessionTable.tableName,
        AGENT_PROCESSOR_FUNCTION_NAME: this.agentProcessor.functionName
      }
    });

    // Grant permissions to the Lambda functions
    this.sessionTable.grantReadWriteData(this.websocketHandler);
    this.sessionTable.grantReadWriteData(this.agentProcessor);

    props.dataStorage.athenaResultBucket.grantReadWrite(this.agentProcessor);

    // Grant access to the data buckets
    props.dataStorage.dataBucket.grantRead(this.agentProcessor); // Write permission is strictly prohibited due to INSERT possibility by Agent

    // Grant Athena permissions to the Lambda functions
    const athenaPolicy = new iam.PolicyStatement({
      actions: [
        'athena:StartQueryExecution',
        'athena:GetQueryExecution',
        'athena:GetQueryResults',
        'athena:StopQueryExecution',
        'glue:GetTable',
        'glue:GetTables',
        'glue:GetDatabase',
        'glue:GetDatabases',
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream'
      ],
      resources: ['*'] // Scope this down in production
    });

    this.agentProcessor.addToRolePolicy(athenaPolicy);

    // Grant Step Functions permissions to the Lambda function
    // Grant permission to start execution of the segment state machine
    props.personalizeSegmentWorkflow.stateMachine.grantStartExecution(this.agentProcessor);

    // Grant DynamoDB permissions to the Lambda function
    props.personalizeStore.personalizeTable.grantReadData(this.agentProcessor);

    // Grant Lambda invoke permissions
    this.agentProcessor.grantInvoke(this.websocketHandler);

    // Create Cognito resources
    this.cognito = new Cognito(this, 'Cognito');

    const webSocketAuthorizerLambda = new nodejs.NodejsFunction(this, 'WebSocketAuthorizerLambda', {
      entry: 'lambda/websocketauth/websocket_authorizer.ts',
      handler: 'handler',
      runtime: lambda.Runtime.NODEJS_22_X,
      timeout: cdk.Duration.seconds(10),
      environment: {
        USER_POOL_ID: this.cognito.userPool.userPoolId,
        USER_POOL_CLIENT_ID: this.cognito.userPoolClient.userPoolClientId
      },
      depsLockFilePath: 'lambda/websocketauth/package-lock.json',
      bundling: {
        commandHooks: {
          beforeBundling: (i, o) => [`cd ${i} && npm ci`],
          afterBundling: (i, o) => [],
          beforeInstall: (i, o) => []
        }
      }
    });

    // Create the WebSocket Lambda Authorizer
    const webSocketAuthorizer = new apigatewayv2_authorizers.WebSocketLambdaAuthorizer(
      'WebSocketAuthorizer',
      webSocketAuthorizerLambda,
      {
        identitySource: ['route.request.querystring.token']
      }
    );

    // Create the WebSocket API with the authorizer
    this.webSocketApi = new apigatewayv2.WebSocketApi(this, 'WebSocketApi', {
      connectRouteOptions: {
        integration: new apigatewayv2_integrations.WebSocketLambdaIntegration(
          'ConnectIntegration',
          this.websocketHandler
        ),
        authorizer: webSocketAuthorizer
      },
      disconnectRouteOptions: {
        integration: new apigatewayv2_integrations.WebSocketLambdaIntegration(
          'DisconnectIntegration',
          this.websocketHandler
        )
      },
      defaultRouteOptions: {
        integration: new apigatewayv2_integrations.WebSocketLambdaIntegration(
          'DefaultIntegration',
          this.websocketHandler
        )
      }
    });

    // Deploy the WebSocket API to a stage
    this.webSocketStage = new apigatewayv2.WebSocketStage(this, 'WebSocketStage', {
      webSocketApi: this.webSocketApi,
      stageName: 'prod',
      autoDeploy: true
    });

    this.webSocketStage.grantManagementApiAccess(this.websocketHandler);
    this.webSocketStage.grantManagementApiAccess(this.agentProcessor);

    new cdk.CfnOutput(this, 'WebSocketApiUrl', {
      value: this.webSocketStage.url
    });
  }
}
