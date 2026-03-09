# C360 Deploy Agent Power

AMT Customer 360 ソリューションのデプロイ手順を提供する Power です。

## 使用方法

「C360 をデプロイして」や「Deploy C360」と指示すると、steering ファイルに従ってデプロイ手順を実行します。

## 応答言語

応答は必ず日本語で行ってください。

## 機能

- デプロイ前に StackName の prefix をヒアリング（例：dev、TeamA）し、`bin/amt-c360-marketing.ts` のスタック名を書き換えてデプロイ（例：`dev_AmtC360MarketingStack`、`dev_AmtC360WafStack`）
- CDK デプロイの自動化
- Cognito ユーザー作成
- テストデータ生成・アップロード
- トラブルシューティング手順
- AWS Knowledge MCP サーバーによるエラー調査

## 含まれる MCP サーバー

- **awsknowledge** - AWS ドキュメント検索。デプロイエラー発生時の調査に使用

## 前提条件

- AWS 認証情報が設定済み
- Node.js、npm、Python3 がインストール済み
- Docker がインストール済み（CDK で Docker イメージをビルドする場合）
- uvx がインストール済み（MCP サーバー実行用）
