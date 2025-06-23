import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { DataStorage } from './data-storage';
import { PersonalizeService } from './personalize';
import { PersonalizeStore } from './solution-version-store';

/**
 * Personalize Segment Workflow Properties
 */
export interface PersonalizeSegmentWorkflowProps {
  dataStorage: DataStorage;
  personalizeService: PersonalizeService;
  personalizeStore: PersonalizeStore;
}

/**
 * Personalize Segment Workflow
 * Manages Step Functions state machine and related Lambda functions for segment creation using Amazon Personalize
 */
export class PersonalizeSegmentWorkflow extends Construct {
  // 外部から参照される必要があるリソース
  public readonly stateMachine: sfn.StateMachine;
  public readonly createPersonalizeSegmentFunction: PythonFunction;

  // 内部実装の詳細、外部からは参照されないリソース
  private readonly checkBatchSegmentJobStatusFunction: PythonFunction;
  private readonly processSegmentResultsFunction: PythonFunction;

  constructor(scope: Construct, id: string, props: PersonalizeSegmentWorkflowProps) {
    super(scope, id);

    const { dataStorage, personalizeService, personalizeStore } = props;

    // Personalizeセグメント作成用のLambda関数を作成
    this.createPersonalizeSegmentFunction = new PythonFunction(this, 'CreatePersonalizeSegment', {
      runtime: lambda.Runtime.PYTHON_3_13,
      entry: 'lambda/create_personalize_segment',
      timeout: cdk.Duration.minutes(15),
      environment: {
        DATASET_GROUP_ARN: personalizeService.datasetGroup.attrDatasetGroupArn,
        DATASET_ARN: personalizeService.interactionDataset.attrDatasetArn,
        OUTPUT_BUCKET: personalizeService.segmentOutputBucket.bucketName,
        OUTPUT_PREFIX: 'segments/',
        PERSONALIZE_ROLE_ARN: personalizeService.personalizeRole.roleArn,
        SOLUTION_VERSION_TABLE: personalizeStore.personalizeTable.tableName,
        ATHENA_DATABASE: dataStorage.glueDatabase.databaseName,
        ATHENA_OUTPUT_LOCATION: `s3://${dataStorage.athenaResultBucket.bucketName}/athena-results/`,
        ATHENA_WORKGROUP: 'primary'
      }
    });

    // Personalizeへのアクセス権限を付与
    this.createPersonalizeSegmentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'personalize:CreateBatchSegmentJob',
          'personalize:DescribeBatchSegmentJob',
          'personalize:ListBatchSegmentJobs'
        ],
        resources: ['*']
      })
    );

    // Athenaへのアクセス権限を付与
    this.createPersonalizeSegmentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
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

    // S3バケットへのアクセス権限を付与
    personalizeService.segmentOutputBucket.grantReadWrite(this.createPersonalizeSegmentFunction);
    dataStorage.athenaResultBucket.grantReadWrite(this.createPersonalizeSegmentFunction);
    dataStorage.dataBucket.grantRead(this.createPersonalizeSegmentFunction);
    // IAM PassRole 権限を追加
    personalizeService.personalizeRole.grantPassRole(this.createPersonalizeSegmentFunction.role!);
    // DynamoDBへのアクセス権限を付与
    personalizeStore.personalizeTable.grantReadWriteData(this.createPersonalizeSegmentFunction);

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
        TARGET_PREFIX: dataStorage.itemBasedSegmentPrefix,
        SOLUTION_VERSION_TABLE: personalizeStore.personalizeTable.tableName
      }
    });

    // S3バケットへのアクセス権限を付与
    personalizeService.segmentOutputBucket.grantRead(this.processSegmentResultsFunction);
    dataStorage.dataBucket.grantReadWrite(this.processSegmentResultsFunction);

    // DynamoDBへのアクセス権限を付与
    personalizeStore.personalizeTable.grantWriteData(this.processSegmentResultsFunction);

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

    // 完了状態
    const completeState = new sfn.Pass(this, 'Complete', {});

    // セグメント結果処理タスク
    const processSegmentResultsTask = new tasks.LambdaInvoke(this, 'ProcessSegmentResultsTask', {
      lambdaFunction: this.processSegmentResultsFunction,
      payload: sfn.TaskInput.fromJsonPathAt('$.batchSegmentJobStatusCheck.Payload'),
      resultPath: '$.processSegmentResults'
    }).next(completeState);

    // Create segment task
    const createSegmentTask = new tasks.LambdaInvoke(this, 'CreateSegmentTask', {
      lambdaFunction: this.createPersonalizeSegmentFunction,
      resultPath: '$.segmentResult'
    });

    // バッチセグメントジョブの待機ループを作成
    const batchSegmentJobWaitLoop = createWaitLoop(
      'BatchSegmentJob',
      this.checkBatchSegmentJobStatusFunction,
      '$.segmentResult.Payload',
      '$.batchSegmentJobStatusCheck',
      '$.batchSegmentJobStatusCheck.Payload.isCompleted',
      processSegmentResultsTask
    );

    // createPersonalizeSegmentFunctionの結果に基づいて分岐
    // isCompleted=trueの場合（すべてのitem_idが既に存在する場合）は直接完了状態へ
    // それ以外の場合はバッチセグメントジョブの待機ループへ
    const segmentChoiceState = new sfn.Choice(this, 'IsSegmentAlreadyComplete')
      .when(sfn.Condition.booleanEquals('$.segmentResult.Payload.isCompleted', true), completeState)
      .otherwise(batchSegmentJobWaitLoop);

    // セグメント作成タスクを分岐に接続
    createSegmentTask.next(segmentChoiceState);

    // Create the state machine
    this.stateMachine = new sfn.StateMachine(this, 'SegmentStateMachine', {
      definition: createSegmentTask
    });
  }
}
