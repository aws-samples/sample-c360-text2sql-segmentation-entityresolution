import * as cdk from 'aws-cdk-lib';
import * as waf from 'aws-cdk-lib/aws-wafv2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
import * as apigw from 'aws-cdk-lib/aws-apigateway';

export interface PublicRestApiProps {
  allowOrigins: string[];
}

export class PublicRestApi extends Construct {
  readonly restApi: apigw.RestApi;
  readonly url: string;

  constructor(scope: Construct, id: string, props: PublicRestApiProps) {
    super(scope, id);

    this.restApi = new apigw.RestApi(this, id, {
      deployOptions: {
        stageName: 'api'
      },
      endpointTypes: [apigw.EndpointType.REGIONAL],
      defaultCorsPreflightOptions: {
        allowOrigins: props.allowOrigins,
        allowMethods: apigw.Cors.ALL_METHODS
      }
    });

    // 40x, 50xの際にAPI Gatewayが直接レスポンスを返す場合も同様にCORSヘッダーを付加するための設定
    {
      this.restApi.addGatewayResponse(`Gwr4xx`, {
        type: apigw.ResponseType.DEFAULT_4XX,
        responseHeaders: {
          'Access-Control-Allow-Origin': props.allowOrigins.map((o) => `'${o}'`).join(',')
        }
      });

      this.restApi.addGatewayResponse(`Gwr5xx`, {
        type: apigw.ResponseType.DEFAULT_5XX,
        responseHeaders: {
          'Access-Control-Allow-Origin': props.allowOrigins.map((o) => `'${o}'`).join(',')
        }
      });
    }

    // cdkではWAFはガワだけつくることとする
    const webAcl = new waf.CfnWebACL(this, 'WebACL', {
      defaultAction: { allow: {} },
      scope: 'REGIONAL',
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: 'WebACL',
        sampledRequestsEnabled: true
      },
      rules: []
    });
    const arn = `arn:aws:apigateway:${cdk.Aws.REGION}::/restapis/${this.restApi.restApiId}/stages/${this.restApi.deploymentStage.stageName}`;
    new waf.CfnWebACLAssociation(this, 'WebAclAssociation', {
      resourceArn: arn,
      webAclArn: webAcl.attrArn
    });

    this.url = this.restApi.url;
  }

  addResource(method: string, path: string[], fn: lambda.Function, authroizer?: apigw.IAuthorizer): void {
    const resource = this.restApi.root.resourceForPath(path.join('/'));
    resource.addMethod(method, new apigw.LambdaIntegration(fn), {
      authorizer: authroizer,
      authorizationType: authroizer?.authorizationType
    });
  }
}
