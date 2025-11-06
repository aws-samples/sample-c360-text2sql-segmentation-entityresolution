# 使い方

## 概要
CSVファイルを分析してAWS Glue Catalogのテーブルスキーマを自動生成し、S3にアップロードするスクリプトです。

## 前提条件
- C360 が AWS アカウントにデプロイ済み
- AWS 認証情報が環境変数で設定済み

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
`./csvfiles`ディレクトリにCSVファイルを配置してください。ヘッダ有りのCSVを期待しています

## 実行

```bash
python csv_to_glue_catalog.py
```

## 動作
1. 既存のGlue Catalogテーブルを全て削除
2. CSVファイルをヘッダーでグループ化
3. Bedrockでスキーマを分析・推測
4. Glue Catalogにテーブルを作成
5. S3にCSVファイルをアップロード