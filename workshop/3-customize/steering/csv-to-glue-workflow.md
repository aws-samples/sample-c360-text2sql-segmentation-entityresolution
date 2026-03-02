---
inclusion: manual
---

# CSV to Glue Catalog ワークフロー

## 概要

デプロイ済みの AmtC360MarketingStack から S3 バケット名と Glue データベース名を取得し、`csvtool/csv_to_glue_catalog.py` の変数を更新してスクリプトを実行する。

## ワークフロー

### 1. CloudFormation から情報を取得

以下のコマンドで AmtC360MarketingStack からリソース情報を取得する。

S3 バケット名:
```bash
aws cloudformation describe-stacks \
  --stack-name AmtC360MarketingStack \
  --query "Stacks[0].Outputs[?OutputKey=='DataStorageDataBucketOutput'].OutputValue" \
  --output text
```

Glue データベース名:
```bash
aws cloudformation list-stack-resources \
  --stack-name AmtC360MarketingStack \
  --query "StackResourceSummaries[?ResourceType=='AWS::Glue::Database'].PhysicalResourceId" \
  --output text
```

### 2. csvtool/csv_to_glue_catalog.py の変数を更新

取得した値で以下の変数を書き換える:

- `S3_BUCKET_NAME` → 取得した S3 バケット名
- `GLUE_DATABASE_NAME` → 取得した Glue データベース名

### 3. スクリプトを実行

```bash
cd csvtool && python csv_to_glue_catalog.py
```

※ 実行前に `csvtool/csvfiles/` 配下に CSV ファイルが配置されていることを確認する。

## 安全性に関する注意事項

- AmtC360MarketingStack のリソース以外を操作しないこと
- ユーザーの CSV ファイルの元データを削除・変更しないこと
