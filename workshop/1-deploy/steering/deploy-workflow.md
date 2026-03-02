---
inclusion: manual
---

# C360 デプロイワークフロー

AMT Customer 360 ソリューションの完全なデプロイ手順です。

## 前提条件

- AWS 認証情報が設定済み
- Node.js、npm、Python3 がインストール済み
- Docker がインストール済み

## デプロイ手順

### 1. Docker 環境のセットアップ（必要な場合）

Docker 権限エラーが発生した場合：

```bash
sudo usermod -aG docker $USER
sudo systemctl restart docker
```

変更を反映するにはターミナルの再起動が必要です。

### 2. CDK デプロイ

```bash
cd <project-dir>
npm ci
npm run cdk bootstrap  # 初回のみ
npm run cdk -- deploy --all --require-approval never
```

### 3. スタック出力の取得

```bash
aws cloudformation describe-stacks \
  --stack-name AmtC360MarketingStack \
  --query "Stacks[0].Outputs" \
  --output table
```

以下の値をメモ：
- `DataStorageDataBucketOutput` - S3バケット名
- `WebAppUrl` - WebアプリURL
- `UserPoolId` - Cognito User Pool ID

### 4. Cognito ユーザー作成

username と、password は、ユーザーの希望を聞いてください

```bash
# User Pool ID を確認
aws cognito-idp list-user-pools --max-results 10

# ユーザー作成
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username user@example.com \
  --temporary-password "TempPass123!" \
  --message-action SUPPRESS
```

### 5. テストデータ生成

```bash
cd <project-dir>
python3 dbloader/gen_testdata.py
```

`dbloader/testdata/` に CSV ファイルが生成されます。

### 6. テストデータを S3 にアップロード

```bash
# upload_to_s3.py の S3_BUCKET_NAME を更新してから実行
cd <project-dir>
python3 dbloader/upload_to_s3.py
```

### 7. データ統合ワークフロー実行

これはやらなくて良いです


## トラブルシューティング

### CloudFormation イベント確認

```bash
aws cloudformation describe-stack-events \
  --stack-name AmtC360MarketingStack \
  --max-items 20
```

### CloudWatch Logs 確認

```bash
# ログストリーム取得
aws logs describe-log-streams \
  --log-group-name "/aws/lambda/<FUNCTION_NAME>" \
  --order-by LastEventTime \
  --descending \
  --max-items 1

# ログイベント取得
aws logs get-log-events \
  --log-group-name "/aws/lambda/<FUNCTION_NAME>" \
  --log-stream-name "<LOG_STREAM_NAME>" \
  --limit 50
```

### AWS Knowledge MCP サーバーで調査

エラーが発生した場合、AWS Knowledge MCP サーバーを使って解決策を検索してください：

- CDK デプロイエラー → CDK や CloudFormation のドキュメントを検索
- Lambda エラー → Lambda のトラブルシューティングガイドを検索
- Cognito エラー → Cognito のドキュメントを検索
- Step Functions エラー → Step Functions のドキュメントを検索

エラーメッセージをそのまま検索クエリに含めると効果的です。

## デプロイオプション

`cdk.json` で設定可能：

```json
{
  "context": {
    "entityResolutionEnabled": false,
    "personalizeEnabled": false
  }
}
```
