#!/usr/bin/env python3
import os
import json
import boto3
import pandas as pd
from pathlib import Path
from collections import defaultdict
import hashlib

# Global variables
S3_BUCKET_NAME = "<ここを実際のs3バケット名に置き換えてください>"
GLUE_DATABASE_NAME = "<ここを実際のGlueデータベース名に置き換えてください>"

BEDROCK_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
CSV_DIRECTORY = "./csvfiles"

# AWS clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
glue = boto3.client("glue")
s3 = boto3.client("s3")


def delete_all_tables(database_name):
    """データベース内の全テーブルを削除"""
    try:
        tables = glue.get_tables(DatabaseName=database_name)
        for table in tables["TableList"]:
            glue.delete_table(DatabaseName=database_name, Name=table["Name"])
            print(f"Deleted table: {table['Name']}")
    except Exception as e:
        print(f"Error deleting tables: {e}")


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
    df = pd.read_csv(csv_path)
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
- テーブル名、説明、各カラムのコメントを日本語で簡潔に記述
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
      "comment": "カラムの説明"
    }}
  ]
}}
"""

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}]}),
    )

    result = json.loads(response["body"].read())
    content = result["content"][0]["text"]

    # JSONを抽出
    start = content.find("{")
    end = content.rfind("}") + 1
    schema_json = json.loads(content[start:end])

    return schema_json


def create_or_update_table(database_name, schema, s3_prefix):
    """Glue Catalogにテーブルを作成または更新"""
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

    glue.create_table(DatabaseName=database_name, TableInput=table_input)
    print(f"Created table: {schema['table_name']}")


def upload_to_s3(file_path, s3_prefix):
    """S3にファイルをアップロード"""
    key = f"{s3_prefix}{os.path.basename(file_path)}"
    s3.upload_file(file_path, S3_BUCKET_NAME, key)
    print(f"Uploaded {file_path} to s3://{S3_BUCKET_NAME}/{key}")


def get_csv_header_hash(csv_path):
    """CSVのヘッダーのハッシュを取得"""
    df = pd.read_csv(csv_path, nrows=0)
    header_str = ",".join(sorted(df.columns))
    return hashlib.md5(header_str.encode()).hexdigest()


def main():
    csv_dir = Path(CSV_DIRECTORY)
    if not csv_dir.exists():
        print(f"Directory {CSV_DIRECTORY} does not exist")
        return

    print(f"Using Glue Database: {GLUE_DATABASE_NAME}")

    # 既存テーブルを全て削除
    delete_all_tables(GLUE_DATABASE_NAME)

    # CSVファイルをヘッダーでグループ化
    header_groups = defaultdict(list)
    for csv_file in csv_dir.glob("*.csv"):
        header_hash = get_csv_header_hash(csv_file)
        header_groups[header_hash].append(csv_file)

    # 各グループを処理
    for header_hash, csv_files in header_groups.items():
        print(f"\nProcessing group with {len(csv_files)} files:")
        for f in csv_files:
            print(f"  - {f.name}")

        # 最初のファイルでスキーマを分析
        schema = analyze_csv_with_bedrock(csv_files[0])
        table_name = schema["table_name"]
        s3_prefix = f"input/{table_name}/"

        # Glue Catalogを更新
        create_or_update_table(GLUE_DATABASE_NAME, schema, s3_prefix)

        # 全ファイルをS3にアップロード
        for csv_file in csv_files:
            upload_to_s3(str(csv_file), s3_prefix)


if __name__ == "__main__":
    main()
