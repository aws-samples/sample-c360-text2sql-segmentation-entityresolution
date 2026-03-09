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

### 0. StackName Prefix のヒアリング

デプロイを開始する前に、ユーザーに StackName の prefix を確認してください。

> 「デプロイするスタック名に prefix を付けますか？（例：dev、TeamA）。prefix を付けると `dev_AmtC360MarketingStack` のようなスタック名になります。不要な場合は空のままで構いません。」

ユーザーが prefix を指定した場合、以降の CDK コマンドに `-c stackPrefix=<PREFIX>` を付与してください。
指定がない場合はデフォルトのスタック名（`AmtC360MarketingStack`、`AmtC360WafStack`）が使用されます。

以降の手順では、prefix が指定された場合のスタック名を `<PREFIX>_AmtC360MarketingStack`、`<PREFIX>_AmtC360WafStack` と表記します。

### 1. Docker 環境のセットアップ（必要な場合）

Docker 権限エラーが発生した場合：

```bash
sudo usermod -aG docker $USER
sudo systemctl restart docker
```

変更を反映するにはターミナルの再起動が必要です。

### 2. CDK デプロイ

prefix なしの場合：
```bash
cd <project-dir>
npm ci
npm run cdk bootstrap  # 初回のみ
npm run cdk -- deploy --all --require-approval never
```

prefix ありの場合（例：dev）：
```bash
cd <project-dir>
npm ci
npm run cdk bootstrap  # 初回のみ
npm run cdk -- deploy --all --require-approval never -c stackPrefix=dev
```

### 3. スタック出力の取得

```bash
aws cloudformation describe-stacks \
  --stack-name <PREFIX>_AmtC360MarketingStack \
  --query "Stacks[0].Outputs" \
  --output table
```

prefix を指定していない場合は `AmtC360MarketingStack` を使用してください。

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
  --stack-name <PREFIX>_AmtC360MarketingStack \
  --max-items 20
```

prefix を指定していない場合は `AmtC360MarketingStack` を使用してください。

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
    "personalizeEnabled": false,
    "stackPrefix": "dev"
  }
}
```
