import * as path from 'node:path';
import { CfnOutput, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import { Distribution, GeoRestriction } from 'aws-cdk-lib/aws-cloudfront';
import { S3BucketOrigin } from 'aws-cdk-lib/aws-cloudfront-origins';
import { Bucket, BlockPublicAccess } from 'aws-cdk-lib/aws-s3';
import { NodejsBuild } from 'deploy-time-build';
import { Construct } from 'constructs';
import { WebBackend } from './webbackend';

export interface FrontendProps extends StackProps {
  backend: WebBackend;
  webAclArn: string;
}

export class Frontend extends Construct {
  constructor(scope: Construct, id: string, props: FrontendProps) {
    super(scope, id);

    const webBucket = new Bucket(this, 'WebBucket', {
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      versioned: false,
      enforceSSL: true,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      publicReadAccess: false
    });

    // CloudFront
    const distribution = new Distribution(this, 'Distribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: S3BucketOrigin.withOriginAccessControl(webBucket)
      },
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html'
        }
      ],
      geoRestriction: GeoRestriction.allowlist('JP'),
      webAclId: props.webAclArn,
      enableLogging: false
    });

    new NodejsBuild(this, 'WebAppBuild', {
      assets: [
        {
          path: path.join(__dirname, '../frontend')
        }
      ],
      nodejsVersion: 20,
      destinationBucket: webBucket,
      distribution: distribution,
      outputSourceDirectory: 'dist',
      buildCommands: ['npm ci', 'npm run build'],
      buildEnvironment: {
        VITE_APP_REGION: Stack.of(this).region,
        VITE_APP_USER_POOL_ID: props.backend.cognito.userPool.userPoolId,
        VITE_APP_USER_POOL_WEB_CLIENT_ID: props.backend.cognito.userPoolClient.userPoolClientId,
        VITE_APP_WEBSOCKET_URL: props.backend.webSocketStage.url,
        VITE_APP_BASEURL: props.backend.restApi.url
      }
    });

    new CfnOutput(this, 'WebAppUrl', {
      key: 'WebAppUrl',
      value: `https://${distribution.distributionDomainName}`,
      description: 'The URL of the web application'
    });
  }
}
