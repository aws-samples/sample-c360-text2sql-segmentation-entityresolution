---
inclusion: manual
---

# CSV to Glue Catalog ワークフロー

## 概要

デプロイ済みのスタックから S3 バケット名と Glue データベース名を取得し、`csvtool/csv_to_glue_catalog.py` の変数を更新してスクリプトを実行する。

※ デプロイ時に stackPrefix を指定した場合、スタック名は `<PREFIX>_AmtC360MarketingStack` となります。ユーザーに確認してください。

## ワークフロー

### 1. CloudFormation から情報を取得

以下のコマンドでスタックからリソース情報を取得する。スタック名はデプロイ時の prefix に応じて変更すること（例：`dev_AmtC360MarketingStack`）。

S3 バケット名:
```bash
aws cloudformation describe-stacks \
  --stack-name <STACK_NAME> \
  --query "Stacks[0].Outputs[?OutputKey=='DataStorageDataBucketOutput'].OutputValue" \
  --output text
```

Glue データベース名:
```bash
aws cloudformation list-stack-resources \
  --stack-name <STACK_NAME> \
  --query "StackResourceSummaries[?ResourceType=='AWS::Glue::Database'].PhysicalResourceId" \
  --output text
```

### 2. Python 依存パッケージの確認

`csvtool/requirements.txt` に記載されたパッケージ（pandas, boto3）がインストール済みか確認する：

```bash
python3 -c "import pandas; import boto3; print('OK')"
```

`OK` が表示されない場合、まず pip でのインストールを試みる：

```bash
pip install -r csvtool/requirements.txt
```

pip が利用できない場合は、システムパッケージでインストールする：

```bash
sudo apt update
sudo apt install -y python3-pandas python3-boto3
```

### 3. csvtool/csv_to_glue_catalog.py の変数を更新

取得した値で以下の変数を書き換える:

- `S3_BUCKET_NAME` → 取得した S3 バケット名
- `GLUE_DATABASE_NAME` → 取得した Glue データベース名

### 4. スクリプトを実行

```bash
cd csvtool && python csv_to_glue_catalog.py
```

※ 実行前に `csvtool/csvfiles/` 配下に CSV ファイルが配置されていることを確認する。

## 安全性に関する注意事項

- スタックのリソース以外を操作しないこと
- ユーザーの CSV ファイルの元データを削除・変更しないこと
