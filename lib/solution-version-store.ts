import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';

/**
 * Personalize Store Properties
 */
export interface PersonalizeStoreProps {}

/**
 * Personalize Store
 * Manages DynamoDB table for storing Personalize-related data:
 * - Solution version ARN
 * - Segment job status
 *
 * The table contains a single record with id="latest" that stores:
 * - solutionVersionArn: The latest solution version ARN
 * - segmentJobId: The ID of the latest segment job (if any)
 * - segmentJobStatus: The status of the latest segment job (RUNNING, COMPLETED, FAILED)
 * - segmentJobItemIds: The item IDs for the latest segment job
 * - segmentJobCreatedAt: When the latest segment job was created
 * - segmentJobCompletedAt: When the latest segment job was completed (if completed)
 * - segmentJobErrorMessage: Error message if the job failed
 */
export class PersonalizeStore extends Construct {
  public readonly personalizeTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: PersonalizeStoreProps) {
    super(scope, id);

    // DynamoDB table for storing Personalize-related data in a single record
    this.personalizeTable = new dynamodb.Table(this, 'PersonalizeTable', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY // For development only, use RETAIN for production
    });
  }
}
