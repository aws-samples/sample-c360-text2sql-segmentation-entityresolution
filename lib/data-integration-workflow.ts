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

/**
 * Data Integration Workflow Properties
 */
export interface DataIntegrationWorkflowProps {
  entityResolutionService: EntityResolutionService;
  dataStorage: DataStorage;
  personalizeService: PersonalizeService;
}

/**
 * Data Integration Workflow
 * Manages Step Functions state machine and related Lambda functions for customer data integration using Entity Resolution
 * and segment creation using Amazon Personalize
 */
export class DataIntegrationWorkflow extends Construct {
  // 外部から参照される必要があるリソース
  public readonly stateMachine: sfn.StateMachine;

  // 内部実装の詳細、外部からは参照されないリソース
  private readonly erStarter: PythonFunction;
  private readonly checkErStatusFunction: PythonFunction;
  private readonly integratedCustomerUpdater: PythonFunction;
  private readonly createPersonalizeDatasetImportJob: PythonFunction;
  private readonly checkDatasetImportJobStatus: PythonFunction;
  private readonly createPersonalizeSolution: PythonFunction;
  private readonly checkSolutionStatus: PythonFunction;
  private readonly createPersonalizeSolutionVersionFunction: PythonFunction;
  private readonly checkSolutionVersionStatusFunction: PythonFunction;
  private readonly createPersonalizeSegmentFunction: PythonFunction;
  private readonly checkBatchSegmentJobStatusFunction: PythonFunction;
  private readonly processSegmentResultsFunction: PythonFunction;

  constructor(scope: Construct, id: string, props: DataIntegrationWorkflowProps) {
    super(scope, id);

    const { entityResolutionService, dataStorage, personalizeService } = props;

    // Entity Resolution実行用のLambda関数を作成
    this.erStarter = new PythonFunction(this, 'RunEntityResolutionFunction', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/erstarter',
      timeout: cdk.Duration.minutes(15),
      environment: {
        WORKFLOW_NAME: entityResolutionService.matchingWorkflow.workflowName
      }
    });
    dataStorage.dataBucket.grantReadWrite(this.erStarter);

    // Entity Resolutionへのアクセス権限を付与
    this.erStarter.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['entityresolution:StartMatchingJob', 'entityresolution:GetMatchingJob'],
        resources: ['*']
      })
    );

    // ERジョブのステータスを確認するLambda関数を作成
    // Step Functionsのポーリングループで使用され、ジョブの完了を検知する
    this.checkErStatusFunction = new PythonFunction(this, 'CheckERStatusFunction', {
      entry: 'lambda/check_er_status',
      runtime: lambda.Runtime.PYTHON_3_13,
      timeout: cdk.Duration.minutes(1),
      environment: {
        WORKFLOW_NAME: entityResolutionService.matchingWorkflow.workflowName
      }
    });
    this.checkErStatusFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['entityresolution:GetMatchingJob'],
        resources: ['*']
      })
    );

    // Entity Resolution の結果を反映するLambda関数を作成
    this.integratedCustomerUpdater = new PythonFunction(this, 'IntegratedCustomerUpdater', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/integrated_customer_updater',
      timeout: cdk.Duration.minutes(15),
      environment: {
        BUCKET_NAME: dataStorage.dataBucket.bucketName,
        SOURCE_PREFIX: `${entityResolutionService.outputPrefix}${entityResolutionService.matchingWorkflowName}/`,
        DEST_PREFIX: dataStorage.integratedCustomerTablePrefix
      }
    });
    dataStorage.dataBucket.grantReadWrite(this.integratedCustomerUpdater);

    // Personalizeデータセットインポートジョブ作成用のLambda関数を作成
    this.createPersonalizeDatasetImportJob = new PythonFunction(this, 'CreatePersonalizeDatasetImportJob', {
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
    this.createPersonalizeDatasetImportJob.addToRolePolicy(
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
    personalizeService.personalizeRole.grantPassRole(this.createPersonalizeDatasetImportJob.role!);

    // S3バケットへのアクセス権限を付与
    dataStorage.dataBucket.grantRead(this.createPersonalizeDatasetImportJob);
    personalizeService.segmentOutputBucket.grantReadWrite(this.createPersonalizeDatasetImportJob);

    // データセットインポートジョブのステータスを確認するLambda関数を作成
    this.checkDatasetImportJobStatus = new PythonFunction(this, 'CheckDatasetImportJobStatus', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/check_dataset_import_job_status',
      timeout: cdk.Duration.minutes(5)
    });

    // Personalizeへのアクセス権限を付与（ステータス確認用）
    this.checkDatasetImportJobStatus.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['personalize:DescribeDatasetImportJob'],
        resources: ['*']
      })
    );

    // Personalizeソリューション作成用のLambda関数を作成
    this.createPersonalizeSolution = new PythonFunction(this, 'CreatePersonalizeSolution', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/create_personalize_solution',
      timeout: cdk.Duration.minutes(5),
      environment: {
        DATASET_GROUP_ARN: personalizeService.datasetGroup.attrDatasetGroupArn,
        RECIPE_ARN: personalizeService.itemAffinityRecipe
      }
    });

    // Personalizeへのアクセス権限を付与
    this.createPersonalizeSolution.addToRolePolicy(
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
    this.checkSolutionStatus = new PythonFunction(this, 'CheckSolutionStatus', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/check_solution_status',
      timeout: cdk.Duration.minutes(5)
    });

    // Personalizeへのアクセス権限を付与（ステータス確認用）
    this.checkSolutionStatus.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['personalize:DescribeSolution'],
        resources: ['*']
      })
    );

    // Personalizeソリューションバージョン作成用のLambda関数を作成
    this.createPersonalizeSolutionVersionFunction = new PythonFunction(this, 'CreatePersonalizeSolutionVersion', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/create_personalize_solution_version',
      timeout: cdk.Duration.minutes(5)
      // SOLUTION_ARNはStep Functionsの前のステップから動的に設定される
    });

    // Personalizeへのアクセス権限を付与
    this.createPersonalizeSolutionVersionFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'personalize:CreateSolutionVersion',
          'personalize:DescribeSolutionVersion',
          'personalize:ListSolutionVersions'
        ],
        resources: ['*']
      })
    );

    // ソリューションバージョンのステータスを確認するLambda関数を作成
    this.checkSolutionVersionStatusFunction = new PythonFunction(this, 'CheckSolutionVersionStatus', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/check_solution_version_status',
      timeout: cdk.Duration.minutes(5)
    });

    // Personalizeへのアクセス権限を付与（ステータス確認用）
    this.checkSolutionVersionStatusFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['personalize:DescribeSolutionVersion'],
        resources: ['*']
      })
    );

    // Personalizeセグメント作成用のLambda関数を作成
    this.createPersonalizeSegmentFunction = new PythonFunction(this, 'CreatePersonalizeSegment', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/create_personalize_segment',
      timeout: cdk.Duration.minutes(15),
      environment: {
        DATASET_GROUP_ARN: personalizeService.datasetGroup.attrDatasetGroupArn,
        DATASET_ARN: personalizeService.interactionDataset.attrDatasetArn,
        ATHENA_BUCKET: dataStorage.athenaResultBucket.bucketName,
        OUTPUT_BUCKET: personalizeService.segmentOutputBucket.bucketName,
        OUTPUT_PREFIX: 'segments/',
        GLUE_DATABASE_NAME: dataStorage.glueDatabase.databaseName,
        PERSONALIZE_ROLE_ARN: personalizeService.personalizeRole.roleArn
      }
    });

    // Athenaへのアクセス権限を付与
    this.createPersonalizeSegmentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'athena:StartQueryExecution',
          'athena:GetQueryExecution',
          'athena:GetQueryResults',
          'glue:GetTable',
          'glue:GetPartitions',
          'glue:GetDatabase',
          'personalize:CreateBatchSegmentJob',
          'personalize:DescribeBatchSegmentJob',
          'personalize:ListBatchSegmentJobs'
        ],
        resources: ['*']
      })
    );

    // S3バケットへのアクセス権限を付与
    dataStorage.dataBucket.grantRead(this.createPersonalizeSegmentFunction);
    dataStorage.athenaResultBucket.grantReadWrite(this.createPersonalizeSegmentFunction);
    personalizeService.segmentOutputBucket.grantReadWrite(this.createPersonalizeSegmentFunction);
    // IAM PassRole 権限を追加
    personalizeService.personalizeRole.grantPassRole(this.createPersonalizeSegmentFunction.role!);

    // Entity Resolution実行タスク
    const erStarterTask = new tasks.LambdaInvoke(this, 'erStarterTask', {
      lambdaFunction: this.erStarter,
      resultPath: '$.erStarterResult'
    });

    // Entity Resolution の結果を反映するLambda関数のタスク
    const integratedCustomerUpdaterTask = new tasks.LambdaInvoke(this, 'IntegratedCustomerUpdaterTask', {
      lambdaFunction: this.integratedCustomerUpdater,
      payload: sfn.TaskInput.fromJsonPathAt('$.erStarterResult.Payload')
    });

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

    // Personalizeデータセットインポートジョブ作成タスク
    const createDatasetImportJobTask = new tasks.LambdaInvoke(this, 'CreateDatasetImportJobTask', {
      lambdaFunction: this.createPersonalizeDatasetImportJob,
      payload: sfn.TaskInput.fromJsonPathAt('$'),
      resultPath: '$.datasetImportJobResult'
    });

    // Personalizeソリューション作成タスク
    const createSolutionTask = new tasks.LambdaInvoke(this, 'CreateSolutionTask', {
      lambdaFunction: this.createPersonalizeSolution,
      payload: sfn.TaskInput.fromJsonPathAt('$'),
      resultPath: '$.solutionResult'
    });

    // Personalizeソリューションバージョン作成タスク
    const createSolutionVersionTask = new tasks.LambdaInvoke(this, 'CreateSolutionVersionTask', {
      lambdaFunction: this.createPersonalizeSolutionVersionFunction,
      payload: sfn.TaskInput.fromObject({
        solutionArn: sfn.JsonPath.stringAt('$.solutionStatusCheck.Payload.solutionArn')
      }),
      resultPath: '$.solutionVersionResult'
    });

    // Personalizeセグメント作成タスク
    const createPersonalizeSegmentTask = new tasks.LambdaInvoke(this, 'CreatePersonalizeSegmentTask', {
      lambdaFunction: this.createPersonalizeSegmentFunction,
      payload: sfn.TaskInput.fromObject({
        solutionVersionArn: sfn.JsonPath.stringAt('$.solutionVersionStatusCheck.Payload.solutionVersionArn')
      }),
      resultPath: '$.segmentResult'
    });

    // バッチセグメントジョブのステータスを確認するLambda関数を作成
    this.checkBatchSegmentJobStatusFunction = new PythonFunction(this, 'CheckBatchSegmentJobStatus', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/check_batch_segment_job_status',
      timeout: cdk.Duration.minutes(5)
    });

    // Personalizeへのアクセス権限を付与（ステータス確認用）
    this.checkBatchSegmentJobStatusFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['personalize:DescribeBatchSegmentJob'],
        resources: ['*']
      })
    );

    // セグメント結果を処理するLambda関数を作成
    this.processSegmentResultsFunction = new PythonFunction(this, 'ProcessSegmentResults', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/process_segment_results',
      timeout: cdk.Duration.minutes(15),
      environment: {
        SEGMENT_BUCKET: personalizeService.segmentOutputBucket.bucketName,
        SEGMENT_PREFIX: 'segments/',
        TARGET_BUCKET: dataStorage.dataBucket.bucketName,
        TARGET_PREFIX: dataStorage.itemBasedSegmentPrefix
      }
    });

    // S3バケットへのアクセス権限を付与
    personalizeService.segmentOutputBucket.grantRead(this.processSegmentResultsFunction);
    dataStorage.dataBucket.grantReadWrite(this.processSegmentResultsFunction);

    // セグメント結果処理タスク
    const processSegmentResultsTask = new tasks.LambdaInvoke(this, 'ProcessSegmentResultsTask', {
      lambdaFunction: this.processSegmentResultsFunction,
      payload: sfn.TaskInput.fromJsonPathAt('$.batchSegmentJobStatusCheck.Payload'),
      resultPath: '$.processSegmentResults'
    }).next(new sfn.Pass(this, 'Complete', {}));

    // バッチセグメントジョブの待機ループを作成
    const batchSegmentJobWaitLoop = createWaitLoop(
      'BatchSegmentJob',
      this.checkBatchSegmentJobStatusFunction,
      '$.segmentResult.Payload',
      '$.batchSegmentJobStatusCheck',
      '$.batchSegmentJobStatusCheck.Payload.isCompleted',
      processSegmentResultsTask
    );

    // セグメント作成タスクを待機ループに接続
    createPersonalizeSegmentTask.next(batchSegmentJobWaitLoop);

    // 各待機ループを作成 - 正しい順序で接続
    const solutionVersionWaitLoop = createWaitLoop(
      'SolutionVersion',
      this.checkSolutionVersionStatusFunction,
      '$.solutionVersionResult.Payload',
      '$.solutionVersionStatusCheck',
      '$.solutionVersionStatusCheck.Payload.isCompleted',
      createPersonalizeSegmentTask
    );

    const solutionWaitLoop = createWaitLoop(
      'Solution',
      this.checkSolutionStatus,
      '$.solutionResult.Payload',
      '$.solutionStatusCheck',
      '$.solutionStatusCheck.Payload.isCompleted',
      createSolutionVersionTask.next(solutionVersionWaitLoop)
    );

    const datasetImportJobWaitLoop = createWaitLoop(
      'DatasetImportJob',
      this.checkDatasetImportJobStatus,
      '$.datasetImportJobResult.Payload',
      '$.datasetImportJobStatusCheck',
      '$.datasetImportJobStatusCheck.Payload.isCompleted',
      createSolutionTask.next(solutionWaitLoop)
    );

    // Entity Resolution ジョブの待機ループを createWaitLoop で作成
    const erWaitLoop = createWaitLoop(
      'EntityResolution',
      this.checkErStatusFunction,
      '$.erStarterResult.Payload',
      '$.erStatusCheck',
      '$.erStatusCheck.Payload.isCompleted',
      integratedCustomerUpdaterTask.next(createDatasetImportJobTask).next(datasetImportJobWaitLoop)
    );

    // erStarterTask を erWaitLoop に接続
    erStarterTask.next(erWaitLoop);

    this.stateMachine = new sfn.StateMachine(this, 'DataIntegrationStateMachine', {
      definition: erStarterTask
    });
  }
}
