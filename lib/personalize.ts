import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as personalize from 'aws-cdk-lib/aws-personalize';
import { Construct } from 'constructs';
import { DataStorage } from './data-storage';

/**
 * Personalize Service Properties
 */
export interface PersonalizeServiceProps {
  dataStorage: DataStorage;
}

/**
 * Personalize Service
 * Manages Amazon Personalize resources and provides resources for segment creation
 */
export class PersonalizeService extends Construct {
  public readonly personalizeRole: iam.Role;
  public readonly datasetGroup: personalize.CfnDatasetGroup;
  public readonly interactionSchema: personalize.CfnSchema;
  public readonly interactionDataset: personalize.CfnDataset;
  public readonly itemAffinityRecipe: string;
  public readonly segmentOutputBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: PersonalizeServiceProps) {
    super(scope, id);

    const { dataStorage } = props;

    this.personalizeRole = new iam.Role(this, 'PersonalizeRole', {
      assumedBy: new iam.ServicePrincipal('personalize.amazonaws.com')
    });

    dataStorage.dataBucket.grantRead(this.personalizeRole);

    this.segmentOutputBucket = new s3.Bucket(this, 'PersonalizeSegmentBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });

    this.segmentOutputBucket.grantReadWrite(this.personalizeRole);
    // https://docs.aws.amazon.com/personalize/latest/dg/granting-personalize-s3-access.html#attach-bucket-policy
    this.segmentOutputBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        principals: [new iam.ServicePrincipal('personalize.amazonaws.com')],
        actions: ['s3:GetObject', 's3:ListBucket', 's3:PutObject'],
        resources: [`${this.segmentOutputBucket.bucketArn}`, `${this.segmentOutputBucket.bucketArn}/*`]
      })
    );

    this.datasetGroup = new personalize.CfnDatasetGroup(this, 'DatasetGroup', {
      name: `${cdk.Stack.of(this).stackName}DatasetGroup`
    });

    this.interactionSchema = new personalize.CfnSchema(this, 'InteractionSchema', {
      name: 'PurchaseInteractionSchema',
      schema: JSON.stringify({
        type: 'record',
        name: 'Interactions',
        namespace: 'com.amazonaws.personalize.schema',
        fields: [
          {
            name: 'USER_ID',
            type: 'string'
          },
          {
            name: 'ITEM_ID',
            type: 'string'
          },
          {
            name: 'TIMESTAMP',
            type: 'long'
          }
        ],
        version: '1.0'
      })
    });

    this.interactionDataset = new personalize.CfnDataset(this, 'InteractionDataset', {
      datasetGroupArn: this.datasetGroup.attrDatasetGroupArn,
      datasetType: 'Interactions',
      name: 'PurchaseInteractions',
      schemaArn: this.interactionSchema.attrSchemaArn
    });

    this.itemAffinityRecipe = 'arn:aws:personalize:::recipe/aws-item-affinity';
  }
}
