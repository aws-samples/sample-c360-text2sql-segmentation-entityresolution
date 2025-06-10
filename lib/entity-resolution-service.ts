import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { CfnMatchingWorkflow, CfnSchemaMapping } from 'aws-cdk-lib/aws-entityresolution';
import { DataStorage } from './data-storage';

/**
 * Entity Resolution Service Properties
 */
export interface EntityResolutionServiceProps {
  dataStorage: DataStorage;
}

/**
 * Manages schema mapping and matching workflow for AWS Entity Resolution
 */
export class EntityResolutionService extends Construct {
  public readonly matchingWorkflow: CfnMatchingWorkflow;
  public readonly outputPrefix: string;
  public readonly matchingWorkflowName: string;

  private readonly customerMasterSchemaMapping: CfnSchemaMapping;
  private readonly subbrandCustomerMasterSchemaMapping: CfnSchemaMapping;
  private readonly serviceRole: iam.Role;

  constructor(scope: Construct, id: string, props: EntityResolutionServiceProps) {
    super(scope, id);

    const { dataStorage } = props;

    this.serviceRole = new iam.Role(this, 'ServiceRole', {
      assumedBy: new iam.ServicePrincipal('entityresolution.amazonaws.com')
    });

    dataStorage.dataBucket.grantReadWrite(this.serviceRole);

    this.serviceRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['glue:GetDatabase', 'glue:GetTable', 'glue:GetPartition', 'glue:GetPartitions'],
        resources: [
          dataStorage.glueDatabase.catalogArn,
          dataStorage.glueDatabase.databaseArn,
          dataStorage.customerMasterTable.tableArn,
          dataStorage.subbrandCustomerMasterTable.tableArn,
          dataStorage.integratedCustomerTable.tableArn
        ]
      })
    );

    dataStorage.customerMasterTable.grantRead(this.serviceRole);
    dataStorage.subbrandCustomerMasterTable.grantRead(this.serviceRole);
    dataStorage.integratedCustomerTable.grantRead(this.serviceRole);

    this.customerMasterSchemaMapping = new CfnSchemaMapping(this, 'CustomerMasterSchemaMapping', {
      schemaName: `${cdk.Stack.of(this).stackName}MainBrandCustomer`,
      mappedInputFields: [
        {
          fieldName: 'customer_id',
          type: 'UNIQUE_ID',
          matchKey: 'customer_id'
        },
        {
          fieldName: 'email',
          type: 'EMAIL_ADDRESS',
          matchKey: 'email'
        },
        {
          fieldName: 'firstname',
          type: 'NAME',
          subType: 'FIRST_NAME',
          matchKey: 'firstname'
        },
        {
          fieldName: 'lastname',
          type: 'NAME',
          subType: 'LAST_NAME',
          matchKey: 'lastname'
        },
        {
          fieldName: 'gender',
          type: 'STRING',
          matchKey: 'gender'
        },
        {
          fieldName: 'age',
          type: 'STRING',
          matchKey: 'age'
        },
        {
          fieldName: 'created_at',
          type: 'DATE',
          matchKey: 'created_at'
        }
      ]
    });

    this.subbrandCustomerMasterSchemaMapping = new CfnSchemaMapping(this, 'SubbrandCustomerMasterSchemaMapping', {
      schemaName: `${cdk.Stack.of(this).stackName}SubBrandCustomer`,
      mappedInputFields: [
        {
          fieldName: 'customer_id',
          type: 'UNIQUE_ID',
          matchKey: 'customer_id'
        },
        {
          fieldName: 'email',
          type: 'EMAIL_ADDRESS',
          matchKey: 'email'
        },
        {
          fieldName: 'firstname',
          type: 'NAME',
          subType: 'FIRST_NAME',
          matchKey: 'firstname'
        },
        {
          fieldName: 'lastname',
          type: 'NAME',
          subType: 'LAST_NAME',
          matchKey: 'lastname'
        },
        {
          fieldName: 'gender',
          type: 'STRING',
          matchKey: 'gender'
        },
        {
          fieldName: 'age',
          type: 'STRING',
          matchKey: 'age'
        },
        {
          fieldName: 'created_at',
          type: 'DATE',
          matchKey: 'created_at'
        }
      ]
    });

    this.outputPrefix = 'er-tmp-output/';
    this.matchingWorkflowName = `${cdk.Stack.of(this).stackName}MatchingWorkflow`;
    this.matchingWorkflow = new CfnMatchingWorkflow(this, 'MatchingWorkflow', {
      workflowName: this.matchingWorkflowName,
      inputSourceConfig: [
        {
          inputSourceArn: dataStorage.customerMasterTable.tableArn,
          schemaArn: this.customerMasterSchemaMapping.attrSchemaArn
        },
        {
          inputSourceArn: dataStorage.subbrandCustomerMasterTable.tableArn,
          schemaArn: this.subbrandCustomerMasterSchemaMapping.attrSchemaArn
        }
      ],
      outputSourceConfig: [
        {
          outputS3Path: `s3://${dataStorage.dataBucket.bucketName}/${this.outputPrefix}`,
          output: [
            {
              name: 'email'
            },
            {
              name: 'firstname'
            },
            {
              name: 'lastname'
            },
            {
              name: 'gender'
            },
            {
              name: 'age'
            },
            {
              name: 'created_at'
            }
          ]
        }
      ],
      resolutionTechniques: {
        resolutionType: 'ML_MATCHING'
      },
      roleArn: this.serviceRole.roleArn
    });
    this.matchingWorkflow.node.addDependency(this.serviceRole);
  }
}
