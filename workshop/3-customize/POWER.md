# C360 Customize Agent Power

デプロイ済みの C360 環境に対して、CSV ファイルを Glue Catalog に Iceberg テーブルとして登録するエージェントです。

## 使用方法

「C360 を カスタマイズして」「customize C360」と指示すると、steering ファイルに従って処理を実行します。

## 応答言語

応答は必ず日本語で行ってください。

## 機能

以下の steering ファイルを順番に実行します：

1. `csv-to-glue-workflow.md` - CloudFormation から S3/Glue 情報を取得し、csvtool スクリプトの変数を更新して実行。Glue Catalog に Iceberg テーブルを登録
2. `update-agent-instruction.md` - solution.md を読み込み、agent_processor.py の AGENT_INSTRUCTION を更新して cdk deploy で再デプロイ
3. `update-web-ui-title.md` - solution.md を読み込み、WEB UI のタイトルを更新して cdk deploy で再デプロイ

## 含まれる MCP サーバー

- **awsknowledge** - AWS ドキュメント検索。エラー発生時の調査に使用

## 前提条件

- AWS 認証情報が設定済み
- `workshop/1-deploy` パワーでデプロイ済み（AmtC360MarketingStack が存在）
- `workshop/2-ai-bpr` パワーで `workshop/2-ai-bpr/solution/solution.md` が生成済み
- uvx がインストール済み（MCP サーバー実行用）
- workshop/2-ai-bpr/data/ 配下に登録したい CSV ファイルが配置済み
