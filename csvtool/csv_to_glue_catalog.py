#!/usr/bin/env python3
import os
import json
import boto3
import pandas as pd
from pathlib import Path
from collections import defaultdict
import hashlib
import time

# Global variables
S3_BUCKET_NAME = "<ここを実際のs3バケット名に置き換えてください>"
GLUE_DATABASE_NAME = "<ここを実際のGlueデータベース名に置き換えてください>"

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

CSV_DIRECTORY = "./workshop/2-ai-bpr/data"

# AWS clients
from botocore.config import Config
config = Config(read_timeout=300, connect_timeout=60, retries={'max_attempts': 3})
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1", config=config)
glue = boto3.client("glue")
s3 = boto3.client("s3")
athena = boto3.client("athena")

# Athena設定
ATHENA_OUTPUT_LOCATION = f's3://{S3_BUCKET_NAME}/athena-results/'


def ensure_database_exists(database_name):
    """データベースの存在を確認（存在しない場合はエラー）"""
    try:
        glue.get_database(Name=database_name)
        print(f"データベースを確認しました: {database_name}")
    except glue.exceptions.EntityNotFoundException:
        print(f"\nエラー: Glueデータベース '{database_name}' が見つかりません。")
        print(f"スクリプトを実行する前に、以下のいずれかを行ってください:")
        print(f"  1. AWS Glueコンソールでデータベース '{database_name}' を作成する")
        print(f"  2. スクリプト冒頭のGLUE_DATABASE_NAME変数を既存のデータベース名に変更する")
        raise SystemExit(1)


class S3Handler:
    """S3操作を管理するクラス"""
    def __init__(self, bucket_name):
        self.bucket = bucket_name
        self.client = s3
    
    def upload(self, file_path, prefix):
        """S3にファイルをアップロード"""
        key = f"{prefix}{os.path.basename(file_path)}"
        self.client.upload_file(file_path, self.bucket, key)
        print(f"Uploaded {file_path} to s3://{self.bucket}/{key}")
        return key
    
    def delete_prefix(self, prefix):
        """S3の指定プレフィックス配下を削除"""
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if 'Contents' in page:
                    objects = [{'Key': obj['Key']} for obj in page['Contents']]
                    self.client.delete_objects(Bucket=self.bucket, Delete={'Objects': objects})
            return True
        except Exception as e:
            print(f"Failed to delete S3 prefix {prefix}: {e}")
            return False


class GlueTableManager:
    """Glueテーブル操作を管理するクラス"""
    def __init__(self, database_name):
        self.database = database_name
        self.client = glue
    
    def delete_all_tables(self):
        """データベース内の全テーブルを削除"""
        try:
            tables = self.client.get_tables(DatabaseName=self.database)
            for table in tables["TableList"]:
                self.client.delete_table(DatabaseName=self.database, Name=table["Name"])
                print(f"Deleted table: {table['Name']}")
        except Exception as e:
            print(f"Error deleting tables: {e}")
    
    def create_csv_table(self, schema, s3_prefix):
        """Glue CatalogにCSVテーブルを作成"""
        columns = []
        for col in schema["columns"]:
            glue_type = {"STRING": "string", "BIG_INT": "bigint", "DOUBLE": "double"}[col["type"]]
            columns.append({"Name": col["name"], "Type": glue_type, "Comment": col["comment"]})

        table_input = {
            "Name": schema["table_name"],
            "Description": schema["description"],
            "StorageDescriptor": {
                "Columns": columns,
                "Location": f"s3://{S3_BUCKET_NAME}/{s3_prefix}",
                "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe",
                    "Parameters": {"field.delim": ",", "skip.header.line.count": "1"},
                },
            },
            "Parameters": {"skip.header.line.count": "1", "classification": "csv"},
        }

        self.client.create_table(DatabaseName=self.database, TableInput=table_input)
        print(f"Created table: {schema['table_name']}")
    
    def update_metadata(self, table_name, schema):
        """IcebergテーブルのDescriptionとカラムCommentを更新"""
        table = self.client.get_table(DatabaseName=self.database, Name=table_name)
        table_input = table['Table']
        
        for key in ['DatabaseName', 'CreateTime', 'UpdateTime', 'CreatedBy', 'IsRegisteredWithLakeFormation', 'CatalogId', 'VersionId', 'IsMultiDialectView']:
            table_input.pop(key, None)
        
        table_input['Description'] = schema['description']
        
        for i, col in enumerate(table_input['StorageDescriptor']['Columns']):
            if i < len(schema['columns']):
                col['Comment'] = schema['columns'][i]['comment']
        
        self.client.update_table(DatabaseName=self.database, TableInput=table_input)
        print(f"Updated metadata for Iceberg table: {table_name}")
    
    def delete_table(self, table_name):
        """テーブルを削除"""
        try:
            self.client.delete_table(DatabaseName=self.database, Name=table_name)
            print(f"Deleted CSV table: {table_name}")
            return True
        except Exception as e:
            print(f"Failed to delete CSV table: {e}")
            return False


def delete_all_tables(database_name):
    """データベース内の全テーブルを削除"""
    manager = GlueTableManager(database_name)
    manager.delete_all_tables()


def get_column_stats(df):
    """カラムごとの統計情報を取得"""
    stats = {}
    for col in df.columns:
        col_data = df[col].dropna()
        stats[col] = {
            "is_all_integer": bool(col_data.astype(str).str.match(r"^-?\d+$").all() if len(col_data) > 0 else False),
            "has_decimal": bool(col_data.astype(str).str.contains(r"\.").any() if len(col_data) > 0 else False),
        }
    return stats


def analyze_csv_with_bedrock(csv_path):
    """BedrockでCSVファイルを分析してスキーマを推測"""
    df = pd.read_csv(csv_path, low_memory=False)
    stats = get_column_stats(df)

    # ヘッダ名、先頭と末尾のデータを取得
    headers = list(df.columns)
    head_data = df.head(20).to_string()
    tail_data = df.tail(20).to_string()

    prompt = f"""
以下のCSVファイルのデータを分析して、Glue Catalogのテーブルスキーマを推測してください。

ファイル名: {os.path.basename(csv_path)}

ヘッダ名: {headers}

統計情報:
{json.dumps(stats, indent=2, ensure_ascii=False)}

先頭20行のデータ:
{head_data}

末尾20行のデータ:
{tail_data}

以下の条件でスキーマを推測してください:
- データ型は STRING, BIG_INT, DOUBLE の3種類のみ使用
- 整数のみの場合はBIG_INT、小数点を含む数値はDOUBLE、それ以外はSTRING
- 日時データもSTRINGとして扱う
- テーブル名を英文字にする
- テーブルの説明(２００文字)を日本語で記述
- カラム名を変えずに、各カラムのコメント（１００文字）をもれなく日本語で記述
- カラムのコメントは、わかりにくい場合は架空のデータ例を含めてわかりやすく記述する（例：「顧客ID（例：C001234）」「日時（例：2024-01-15 10:30:00）」）
- 個人情報（氏名、電話番号、住所など）は実際のデータから抜き出さず、フォーマットを揃えた架空の例を使用する

以下のJSON形式で回答してください:
{{
  "table_name": "テーブル名",
  "description": "テーブルの説明",
  "columns": [
    {{
      "name": "カラム名",
      "type": "STRING|BIG_INT|DOUBLE",
      "comment": "カラムのコメント"
    }}
  ]
}}
"""

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 10000, "messages": [{"role": "user", "content": prompt}]}),
    )

    result = json.loads(response["body"].read())
    content = result["content"][0]["text"]

    # JSONを抽出（複数の方法を試行）
    import re
    
    # マークダウンコードブロック内のJSONを探す
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_match:
        try:
            schema_json = json.loads(json_match.group(1))
            return schema_json
        except json.JSONDecodeError:
            pass
    
    # 通常のJSON抽出を試行
    try:
        start = content.find("{")
        end = content.rfind("}") + 1
        schema_json = json.loads(content[start:end])
        return schema_json
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from Bedrock response. Content:\n{content}")
        raise


def wait_for_query(query_execution_id, timeout=300):
    """Athenaクエリの完了を待機"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = status['QueryExecution']['Status']['State']
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            return state
        time.sleep(2)
    return 'TIMEOUT'


def detect_encoding(csv_path):
    """CSVファイルのエンコーディングを検出"""
    for encoding in ['utf-8', 'shift-jis', 'cp932']:
        try:
            with open(csv_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not detect encoding for {csv_path}")

def convert_to_utf8(csv_path):
    """CSVファイルをUTF-8に変換"""
    encoding = detect_encoding(csv_path)
    if encoding != 'utf-8':
        with open(csv_path, 'r', encoding=encoding) as f:
            content = f.read()
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write(content)

def get_csv_header_hash(csv_path):
    """CSVのヘッダーのハッシュを取得"""
    df = pd.read_csv(csv_path, nrows=0, encoding='utf-8')
    header_str = ",".join(sorted(df.columns))
    return hashlib.md5(header_str.encode()).hexdigest()


def execute_athena_ctas(table_name, columns, database_name, schema):
    """Athena CTASでCSVテーブルをIcebergに変換"""
    s3_handler = S3Handler(S3_BUCKET_NAME)
    glue_manager = GlueTableManager(database_name)
    
    iceberg_prefix = f'iceberg/{table_name}/'
    s3_handler.delete_prefix(iceberg_prefix)
    
    column_list = ', '.join([f'"{col["Name"]}"' for col in columns])
    
    query = f"""
    CREATE TABLE {table_name}
    WITH (
      table_type = 'ICEBERG',
      format = 'PARQUET',
      location = 's3://{S3_BUCKET_NAME}/iceberg/{table_name}/',
      is_external = false
    )
    AS SELECT {column_list}
    FROM {table_name}_csv
    """
    
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database_name},
        ResultConfiguration={'OutputLocation': ATHENA_OUTPUT_LOCATION}
    )
    
    query_execution_id = response['QueryExecutionId']
    state = wait_for_query(query_execution_id)
    
    if state == 'SUCCEEDED':
        glue_manager.update_metadata(table_name, schema)
        return True
    
    return False


def process_csv_group(csv_files, database_name):
    """CSVファイルグループを処理"""
    s3_handler = S3Handler(S3_BUCKET_NAME)
    glue_manager = GlueTableManager(database_name)
    
    print(f"\nProcessing group with {len(csv_files)} files:")
    for f in csv_files:
        print(f"  - {f.name}")

    # 最初のファイルでスキーマを分析
    schema = analyze_csv_with_bedrock(csv_files[0])
    table_name = schema["table_name"]
    
    # CSVテーブル作成(一時的に_csv接尾辞)
    csv_table_name = f"{table_name}_csv"
    schema["table_name"] = csv_table_name
    s3_prefix = f"input/{csv_table_name}/"
    
    # Glue Catalogを更新
    glue_manager.create_csv_table(schema, s3_prefix)

    # 全ファイルをS3にアップロード
    for csv_file in csv_files:
        s3_handler.upload(str(csv_file), s3_prefix)
    
    # Athena CTASでIcebergテーブル作成
    columns = [{"Name": col["name"]} for col in schema["columns"]]
    if execute_athena_ctas(table_name, columns, database_name, schema):
        print(f"Created Iceberg table: {table_name}")
        glue_manager.delete_table(f'{table_name}_csv')
    else:
        print(f"Failed to create Iceberg table, keeping CSV table: {csv_table_name}")


def main():
    csv_dir = Path(CSV_DIRECTORY)
    if not csv_dir.exists():
        print(f"Directory {CSV_DIRECTORY} does not exist")
        return

    print(f"Using Glue Database: {GLUE_DATABASE_NAME}")

    # データベースが存在することを確認
    ensure_database_exists(GLUE_DATABASE_NAME)

    # 既存テーブルを全て削除
    delete_all_tables(GLUE_DATABASE_NAME)

    # CSVファイルをUTF-8に変換
    for csv_file in csv_dir.glob("*.csv"):
        convert_to_utf8(csv_file)

    # CSVファイルをヘッダーでグループ化
    header_groups = defaultdict(list)
    for csv_file in csv_dir.glob("*.csv"):
        header_hash = get_csv_header_hash(csv_file)
        header_groups[header_hash].append(csv_file)

    # 各グループを処理
    for header_hash, csv_files in header_groups.items():
        process_csv_group(csv_files, GLUE_DATABASE_NAME)


if __name__ == "__main__":
    main()
