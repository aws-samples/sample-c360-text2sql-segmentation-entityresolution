# 使い方

## 概要
CSVファイルを分析してAWS Glue Catalogのテーブルスキーマを自動生成し、Iceberg形式のテーブルとしてS3に保存するスクリプトです。

## 前提条件
- C360 が AWS アカウントにデプロイ済み
- AWS 認証情報が環境変数で設定済み
- **AWS Glueデータベースが事前に作成されていること**
- Bedrock モデルアクセス許可（us-east-1リージョンでClaude 3.7 Sonnetが有効化されていること）

## セットアップ

1. 依存関係をインストール
```bash
pip install -r requirements.txt
```

2. スクリプトの設定を編集
`csv_to_glue_catalog.py`の冒頭で以下の変数を設定：
```python
S3_BUCKET_NAME = "<ここを実際のs3バケット名に置き換えてください>"
GLUE_DATABASE_NAME = "<ここを実際のGlueデータベース名に置き換えてください>"
```

3. CSVファイルを配置
`./csvfiles`ディレクトリにCSVファイルを配置してください。**ヘッダ行は必須です**

## 実行

```bash
python csv_to_glue_catalog.py
```

## 動作
1. Glueデータベースの存在確認（存在しない場合はエラーで中断）
2. 既存のGlue Catalogテーブルを全て削除
3. CSVファイルをUTF-8に変換（Shift-JIS、CP932にも対応）
4. CSVファイルをヘッダーでグループ化
5. 各グループごとにBedrockでスキーマを分析・推測
6. 一時的なCSV形式のGlue Catalogテーブルを作成
7. S3にCSVファイルをアップロード
8. Athena CTASでIcebergテーブルに変換
9. 一時的なCSVテーブルを削除

## エラー対処

### データベースが見つからない場合
以下のエラーが表示された場合:
```
エラー: Glueデータベース 'xxx' が見つかりません。
```

対処方法:
1. AWS Glueコンソールで指定したデータベース名を作成する
2. スクリプト冒頭の`GLUE_DATABASE_NAME`変数を既存のデータベース名に変更する

## 注意事項
- **既存テーブルが全て削除されます**: スクリプト実行時に指定したデータベース内の全テーブルが削除されます
- **Icebergテーブルとして作成**: 最終的なテーブルはApache Iceberg形式で作成されます
- **Athena出力場所**: クエリ結果は`s3://{bucket}/athena-results/`に保存されます

## 技術詳細

### 使用するAWSサービス
- Amazon Bedrock (Claude 3.7 Sonnet)
- AWS Glue Catalog
- Amazon S3
- Amazon Athena

### サポートするデータ型
- STRING: 文字列、日時データ
- BIG_INT: 整数
- DOUBLE: 小数点を含む数値

### エンコーディング対応
- UTF-8
- Shift-JIS