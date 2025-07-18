import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { EntityResolutionService } from './entity-resolution-service';
import { DataStorage } from './data-storage';
import { PersonalizeService } from './personalize';
import { PersonalizeStore } from './solution-version-store';

/**
 * Data Integration Workflow Properties
 */
export interface DataIntegrationWorkflowProps {
  entityResolutionService?: EntityResolutionService;
  dataStorage: DataStorage;
  personalizeService?: PersonalizeService;
  personalizeStore?: PersonalizeStore;
}

/**
 * Data Integration Workflow
 * Manages Step Functions state machine and related Lambda functions for customer data integration using Entity Resolution
 * and segment creation using Amazon Personalize
 */
export class DataIntegrationWorkflow extends Construct {
  // 外部から参照される必要があるリソース
  public readonly stateMachine?: sfn.StateMachine;

  constructor(scope: Construct, id: string, props: DataIntegrationWorkflowProps) {
    super(scope, id);

    const { entityResolutionService, dataStorage, personalizeService, personalizeStore } = props;

    // 両方のサービスがない場合は何も作成しない
    if (!entityResolutionService && !(personalizeService && personalizeStore)) {
      return;
    }

    // 共通の待機ループ作成関数
    const createWaitLoop = (
      id: string,
      checkFunction: lambda.IFunction,
      payloadPath: string,
      resultPath: string,
      completionPath: string,
      nextState: sfn.IChainable
    ) => {
      // waitステート
      const waitState = new sfn.Wait(this, `${id}Waiter`, {
        time: sfn.WaitTime.duration(cdk.Duration.seconds(30))
      });

      // ステータス確認タスク
      const checkTask = new tasks.LambdaInvoke(this, `${id}CheckTask`, {
        lambdaFunction: checkFunction,
        payload: sfn.TaskInput.fromJsonPathAt(payloadPath),
        resultPath: resultPath
      });

      // 完了チェック
      const choiceState = new sfn.Choice(this, `Is${id}Complete`)
        .when(sfn.Condition.booleanEquals(completionPath, true), nextState)
        .otherwise(waitState);

      // 待機ループを設定
      waitState.next(checkTask).next(choiceState);

      return waitState;
    };

    // Complete state
    const completeState = new sfn.Pass(this, 'Complete', {});

    // Entity Resolution ワークフローを作成する関数
    const createEntityResolutionWorkflow = (nextState: sfn.IChainable): sfn.IChainable => {
      if (!entityResolutionService) {
        throw new Error('Entity Resolution Service is required');
      }

      // Lambda関数を作成
      const erStarter = new PythonFunction(this, 'RunEntityResolutionFunction', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/erstarter',
        timeout: cdk.Duration.minutes(15),
        environment: {
          WORKFLOW_NAME: entityResolutionService.matchingWorkflow.workflowName
        }
      });
      dataStorage.dataBucket.grantReadWrite(erStarter);

      // Entity Resolutionへのアクセス権限を付与
      erStarter.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['entityresolution:StartMatchingJob', 'entityresolution:GetMatchingJob'],
          resources: ['*']
        })
      );

      // ERジョブのステータスを確認するLambda関数を作成
      const checkErStatusFunction = new PythonFunction(this, 'CheckERStatusFunction', {
        entry: 'lambda/check_er_status',
        runtime: lambda.Runtime.PYTHON_3_13,
        timeout: cdk.Duration.minutes(1),
        environment: {
          WORKFLOW_NAME: entityResolutionService.matchingWorkflow.workflowName
        }
      });
      checkErStatusFunction.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['entityresolution:GetMatchingJob'],
          resources: ['*']
        })
      );

      // Entity Resolution の結果を反映するLambda関数を作成
      const integratedCustomerUpdater = new PythonFunction(this, 'IntegratedCustomerUpdater', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/integrated_customer_updater',
        timeout: cdk.Duration.minutes(15),
        environment: {
          BUCKET_NAME: dataStorage.dataBucket.bucketName,
          SOURCE_PREFIX: `${entityResolutionService.outputPrefix}${entityResolutionService.matchingWorkflowName}/`,
          DEST_PREFIX: dataStorage.integratedCustomerTablePrefix
        }
      });
      dataStorage.dataBucket.grantReadWrite(integratedCustomerUpdater);

      // タスクを作成
      const erStarterTask = new tasks.LambdaInvoke(this, 'erStarterTask', {
        lambdaFunction: erStarter,
        resultPath: '$.erStarterResult'
      });

      const integratedCustomerUpdaterTask = new tasks.LambdaInvoke(this, 'IntegratedCustomerUpdaterTask', {
        lambdaFunction: integratedCustomerUpdater,
        payload: sfn.TaskInput.fromJsonPathAt('$.erStarterResult.Payload')
      });

      // Entity Resolution ジョブの待機ループを作成
      const erWaitLoop = createWaitLoop(
        'EntityResolution',
        checkErStatusFunction,
        '$.erStarterResult.Payload',
        '$.erStatusCheck',
        '$.erStatusCheck.Payload.isCompleted',
        integratedCustomerUpdaterTask.next(nextState)
      );

      return erStarterTask.next(erWaitLoop);
    };

    // Personalize ワークフローを作成する関数
    const createPersonalizeWorkflow = (): sfn.IChainable => {
      if (!personalizeService || !personalizeStore) {
        throw new Error('Personalize Service and Store are required');
      }

      // Lambda関数を作成
      const createPersonalizeDatasetImportJob = new PythonFunction(this, 'CreatePersonalizeDatasetImportJob', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/create_personalize_dataset_import_job',
        timeout: cdk.Duration.minutes(15),
        environment: {
          DATASET_ARN: personalizeService.interactionDataset.attrDatasetArn,
          OUTPUT_BUCKET: personalizeService.segmentOutputBucket.bucketName,
          GLUE_DATABASE_NAME: dataStorage.glueDatabase.databaseName,
          PERSONALIZE_ROLE_ARN: personalizeService.personalizeRole.roleArn
        }
      });

      // Personalizeへのアクセス権限を付与
      createPersonalizeDatasetImportJob.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            'personalize:CreateDatasetImportJob',
            'personalize:DescribeDatasetImportJob',
            'personalize:ListDatasetImportJobs',
            'athena:StartQueryExecution',
            'athena:GetQueryExecution',
            'athena:GetQueryResults',
            'glue:GetTable',
            'glue:GetPartitions',
            'glue:GetDatabase'
          ],
          resources: ['*']
        })
      );

      // IAM PassRole 権限を追加
      personalizeService.personalizeRole.grantPassRole(createPersonalizeDatasetImportJob.role!);

      // S3バケットへのアクセス権限を付与
      dataStorage.dataBucket.grantRead(createPersonalizeDatasetImportJob);
      personalizeService.segmentOutputBucket.grantReadWrite(createPersonalizeDatasetImportJob);

      // データセットインポートジョブのステータスを確認するLambda関数を作成
      const checkDatasetImportJobStatus = new PythonFunction(this, 'CheckDatasetImportJobStatus', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/check_dataset_import_job_status',
        timeout: cdk.Duration.minutes(5)
      });

      checkDatasetImportJobStatus.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['personalize:DescribeDatasetImportJob'],
          resources: ['*']
        })
      );

      // Personalizeソリューション作成用のLambda関数を作成
      const createPersonalizeSolution = new PythonFunction(this, 'CreatePersonalizeSolution', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/create_personalize_solution',
        timeout: cdk.Duration.minutes(5),
        environment: {
          DATASET_GROUP_ARN: personalizeService.datasetGroup.attrDatasetGroupArn,
          RECIPE_ARN: personalizeService.itemAffinityRecipe
        }
      });

      createPersonalizeSolution.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            'personalize:CreateSolution',
            'personalize:DescribeSolution',
            'personalize:ListSolutions',
            'personalize:DeleteSolution'
          ],
          resources: ['*']
        })
      );

      // ソリューションのステータスを確認するLambda関数を作成
      const checkSolutionStatus = new PythonFunction(this, 'CheckSolutionStatus', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/check_solution_status',
        timeout: cdk.Duration.minutes(5)
      });

      checkSolutionStatus.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['personalize:DescribeSolution'],
          resources: ['*']
        })
      );

      // Personalizeソリューションバージョン作成用のLambda関数を作成
      const createPersonalizeSolutionVersionFunction = new PythonFunction(this, 'CreatePersonalizeSolutionVersion', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/create_personalize_solution_version',
        timeout: cdk.Duration.minutes(5),
        environment: {
          TARGET_BUCKET: dataStorage.dataBucket.bucketName,
          TARGET_PREFIX: dataStorage.itemBasedSegmentPrefix
        }
      });

      createPersonalizeSolutionVersionFunction.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            'personalize:CreateSolutionVersion',
            'personalize:DescribeSolutionVersion',
            'personalize:ListSolutionVersions'
          ],
          resources: ['*']
        })
      );

      dataStorage.dataBucket.grantReadWrite(createPersonalizeSolutionVersionFunction);

      // ソリューションバージョンのステータスを確認するLambda関数を作成
      const checkSolutionVersionStatusFunction = new PythonFunction(this, 'CheckSolutionVersionStatus', {
        runtime: lambda.Runtime.PYTHON_3_13,
        entry: 'lambda/check_solution_version_status',
        timeout: cdk.Duration.minutes(5),
        environment: {
          SOLUTION_VERSION_TABLE: personalizeStore.personalizeTable.tableName
        }
      });

      checkSolutionVersionStatusFunction.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['personalize:DescribeSolutionVersion'],
          resources: ['*']
        })
      );

      personalizeStore.personalizeTable.grantWriteData(checkSolutionVersionStatusFunction);

      // タスクを作成
      const createDatasetImportJobTask = new tasks.LambdaInvoke(this, 'CreateDatasetImportJobTask', {
        lambdaFunction: createPersonalizeDatasetImportJob,
        payload: sfn.TaskInput.fromJsonPathAt('$'),
        resultPath: '$.datasetImportJobResult'
      });

      const createSolutionTask = new tasks.LambdaInvoke(this, 'CreateSolutionTask', {
        lambdaFunction: createPersonalizeSolution,
        payload: sfn.TaskInput.fromJsonPathAt('$'),
        resultPath: '$.solutionResult'
      });

      const createSolutionVersionTask = new tasks.LambdaInvoke(this, 'CreateSolutionVersionTask', {
        lambdaFunction: createPersonalizeSolutionVersionFunction,
        payload: sfn.TaskInput.fromObject({
          solutionArn: sfn.JsonPath.stringAt('$.solutionStatusCheck.Payload.solutionArn')
        }),
        resultPath: '$.solutionVersionResult'
      });

      // 各待機ループを作成
      const solutionVersionWaitLoop = createWaitLoop(
        'SolutionVersion',
        checkSolutionVersionStatusFunction,
        '$.solutionVersionResult.Payload',
        '$.solutionVersionStatusCheck',
        '$.solutionVersionStatusCheck.Payload.isCompleted',
        completeState
      );

      const solutionWaitLoop = createWaitLoop(
        'Solution',
        checkSolutionStatus,
        '$.solutionResult.Payload',
        '$.solutionStatusCheck',
        '$.solutionStatusCheck.Payload.isCompleted',
        createSolutionVersionTask.next(solutionVersionWaitLoop)
      );

      const datasetImportJobWaitLoop = createWaitLoop(
        'DatasetImportJob',
        checkDatasetImportJobStatus,
        '$.datasetImportJobResult.Payload',
        '$.datasetImportJobStatusCheck',
        '$.datasetImportJobStatusCheck.Payload.isCompleted',
        createSolutionTask.next(solutionWaitLoop)
      );

      return createDatasetImportJobTask.next(datasetImportJobWaitLoop);
    };

    // ワークフローの定義を構築
    let workflowDefinition: sfn.IChainable;

    const hasEntityResolution = !!entityResolutionService;
    const hasPersonalize = !!(personalizeService && personalizeStore);

    if (hasEntityResolution && hasPersonalize) {
      // 両方のサービスがある場合: Entity Resolution → Personalize
      const personalizeWorkflow = createPersonalizeWorkflow();
      workflowDefinition = createEntityResolutionWorkflow(personalizeWorkflow);
    } else if (hasEntityResolution) {
      // Entity Resolutionのみの場合
      workflowDefinition = createEntityResolutionWorkflow(completeState);
    } else if (hasPersonalize) {
      // Personalizeのみの場合
      workflowDefinition = createPersonalizeWorkflow();
    } else {
      // 両方ない場合（この条件は最初のチェックで除外されているはずだが、念のため）
      workflowDefinition = completeState;
    }

    this.stateMachine = new sfn.StateMachine(this, 'DataIntegrationStateMachine', {
      definition: workflowDefinition
    });
  }
}
