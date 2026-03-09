# AgentCore CodeInterpreter によるグラフ生成機能の追加

## 概要

sample-c360-text2sql-segmentation-entityresolution リポジトリに、Amazon Bedrock AgentCore CodeInterpreter を使ったグラフ生成機能を追加するカスタマイズ手順です。

ユーザーがチャットで「グラフを作って」と依頼すると、エージェントが：
1. Athena で SQL を実行してデータを取得
2. AgentCore CodeInterpreter のサンドボックスで matplotlib を使ってグラフを生成
3. 生成された画像を S3 にアップロードし、presigned URL を発行
4. フロントエンドのチャット UI にグラフ画像をインライン表示

## 変更対象ファイル（6ファイル）

| ファイル | 変更内容 |
|---------|---------|
| `lambda/webbackend/requirements.txt` | strands-agents のバージョンを 1.x に更新 |
| `lambda/webbackend/agent_processor.py` | execute_chart_code ツール追加、画像URL抽出ロジック追加 |
| `lambda/webbackend/sessionutils.py` | filter_messages_for_response に chart_image_urls 引数追加 |
| `frontend/src/hooks/useChat.ts` | Message 型に `image` ロール追加 |
| `frontend/src/components/ChatInterface.tsx` | image ロールの表示、markdown 内画像の max-width 制御 |
| `lib/webbackend.ts` | CodeInterpreter IAM ポリシー追加、環境変数追加 |

---

## 変更詳細

### 1. `lambda/webbackend/requirements.txt`

strands-agents を 0.1.5 から 1.x 以上に更新。bedrock-agentcore は不要（boto3 で直接呼び出すため）。

```diff
 aws-lambda-powertools>=2.0.0
-strands-agents==0.1.5
+strands-agents>=1.0.0
```

### 2. `lambda/webbackend/agent_processor.py`

#### 2a. import の変更

```diff
 from strands import Agent, tool
 from strands.models import BedrockModel
-# （strands_tools や bedrock_agentcore の import は不要）
```

#### 2b. 環境変数・定数の追加（BEDROCK_MODEL_ID の後に追加）

```python
CODE_INTERPRETER_REGION = os.environ.get("CODE_INTERPRETER_REGION", "us-west-2")
```

```python
# S3 bucket for chart images (derived from Athena output location)
CHART_IMAGE_BUCKET = ATHENA_OUTPUT_LOCATION.replace("s3://", "").split("/")[0]
```

#### 2c. AGENT_INSTRUCTION のツール説明にグラフツールを追加

ツール一覧に以下を追加：
```
- execute_chart_code: Executes Python code in a secure sandbox to generate charts/graphs using matplotlib.
  The sandbox has pandas, numpy, matplotlib pre-installed.
  Generated charts are automatically uploaded to S3 and presigned URLs are returned.
```

プロセス説明に以下を追加：
```
5. When visualization would help understanding (e.g., trends, comparisons, distributions),
   use execute_chart_code to generate charts with matplotlib.
   You may generate zero or multiple charts per response as appropriate.

When generating charts with execute_chart_code:
- matplotlib.use('Agg') is already set, do NOT call it again.
- Do NOT use seaborn. Use only matplotlib.
- IMPORTANT: Use English for all chart labels, titles, axis labels, and legends
  because the sandbox does not have Japanese fonts.
  Explain the chart in Japanese in your text response.
- Include clear titles, axis labels, and legends
- Choose appropriate chart types (bar, line, pie, scatter, etc.) based on the data
- The tool returns presigned URLs for the generated chart images.
  Include these URLs in your response using markdown image syntax: ![Chart description](URL)
```

#### 2d. execute_chart_code ツールの追加（create_downloadable_url の後に追加）

```python
@tool
def execute_chart_code(python_code: str, description: str = "") -> str:
    """
    Execute Python code in a secure sandbox to generate charts/graphs using matplotlib.
    Generated chart images are automatically uploaded to S3 and presigned URLs are returned.
    """
    wrapped_code = (
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import warnings\n"
        "warnings.filterwarnings('ignore')\n"
        "import matplotlib.pyplot as plt\n"
        "import base64, io, json\n"
        "_captured_images = []\n"
        "_orig_show = plt.show\n"
        "def _cap():\n"
        "    for _i in plt.get_fignums():\n"
        "        _b = io.BytesIO()\n"
        "        plt.figure(_i).savefig(_b, format='png', bbox_inches='tight', dpi=150)\n"
        "        _b.seek(0)\n"
        "        _captured_images.append({'i': _i, 'd': base64.b64encode(_b.read()).decode()})\n"
        "def _pshow(*a, **k):\n"
        "    _cap()\n"
        "plt.show = _pshow\n"
        + python_code + "\n"
        "_cap()\n"
        "'__CHART_IMG__' + json.dumps(_captured_images) + '__CHART_END__' if _captured_images else 'NO_CHARTS'\n"
    )

    agentcore_client = boto3.client("bedrock-agentcore", region_name=CODE_INTERPRETER_REGION)
    session_id = None
    try:
        session_resp = agentcore_client.start_code_interpreter_session(
            codeInterpreterIdentifier="aws.codeinterpreter.v1",
            name=f"chart-{uuid.uuid4().hex[:8]}",
            sessionTimeoutSeconds=300
        )
        session_id = session_resp["sessionId"]

        exec_resp = agentcore_client.invoke_code_interpreter(
            codeInterpreterIdentifier="aws.codeinterpreter.v1",
            sessionId=session_id,
            name="executeCode",
            arguments={"language": "python", "code": wrapped_code}
        )

        all_text = []
        for event in exec_resp.get("stream", []):
            if "result" in event:
                result = event["result"]
                for c in result.get("content", []):
                    if c.get("type") == "text" and c.get("text"):
                        all_text.append(c["text"])
                sc = result.get("structuredContent", {})
                if sc.get("stdout"):
                    all_text.append(sc["stdout"])

        stdout = "\n".join(all_text)

        image_urls = []
        clean_output = stdout
        if "__CHART_IMG__" in stdout and "__CHART_END__" in stdout:
            start = stdout.find("__CHART_IMG__") + len("__CHART_IMG__")
            end = stdout.find("__CHART_END__")
            img_json = stdout[start:end]
            clean_output = stdout[:stdout.find("__CHART_IMG__")].strip()
            imgs = json.loads(img_json)
            for img_data in imgs:
                img_bytes = base64.b64decode(img_data['d'])
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_key = f"chart-images/{ts}_{uuid.uuid4().hex[:8]}.png"
                s3.put_object(Bucket=CHART_IMAGE_BUCKET, Key=file_key, Body=img_bytes, ContentType='image/png')
                url = s3.generate_presigned_url('get_object', Params={'Bucket': CHART_IMAGE_BUCKET, 'Key': file_key}, ExpiresIn=3600)
                image_urls.append(url)

        if image_urls:
            parts = []
            if clean_output:
                parts.append(f"Code output:\n{clean_output}")
            parts.append(f"Generated {len(image_urls)} chart(s):")
            for i, url in enumerate(image_urls):
                parts.append(f"Chart {i+1} URL: {url}")
            return "\n".join(parts)
        elif clean_output:
            return f"Code output (no charts generated):\n{clean_output}"
        else:
            return "Code executed successfully (no output)"
    except Exception as e:
        return f"Error executing chart code: {str(e)}"
    finally:
        if session_id:
            try:
                agentcore_client.stop_code_interpreter_session(
                    codeInterpreterIdentifier="aws.codeinterpreter.v1", sessionId=session_id)
            except Exception:
                pass
```

#### 2e. extract_chart_urls_from_messages 関数の追加

```python
def extract_chart_urls_from_messages(messages):
    import re
    image_urls = []
    for message in messages:
        for content_item in message.get("content", []):
            if "toolResult" not in content_item:
                continue
            tool_result = content_item["toolResult"]
            for result_content in tool_result.get("content", []):
                text = result_content.get("text", "")
                if "Chart" in text and "URL:" in text:
                    url_matches = re.findall(r'Chart \d+ URL: (https://[^\s]+)', text)
                    image_urls.extend(url_matches)
    return image_urls
```

#### 2f. handler 関数内の変更

ツールリストに `execute_chart_code` を追加：
```python
tools = [execute_sql_query, create_downloadable_url, execute_chart_code]
```

エージェント応答後に画像URL抽出を追加：
```python
chart_image_urls = extract_chart_urls_from_messages(agent.messages)
```

filter_messages_for_response の呼び出しに chart_image_urls を渡す：
```python
conversation_history = filter_messages_for_response(agent.messages, chart_image_urls)
```

### 3. `lambda/webbackend/sessionutils.py`

#### filter_messages_for_response のシグネチャ変更

```diff
-def filter_messages_for_response(messages):
+def filter_messages_for_response(messages, chart_image_urls=None):
```

#### 関数末尾に画像メッセージ追加ロジック

```python
    # Append chart image URLs as special image messages
    if chart_image_urls:
        for url in chart_image_urls:
            filtered_messages.append({"role": "image", "content": [{"text": url}]})

    return filtered_messages
```

### 4. `frontend/src/hooks/useChat.ts`

Message 型に `image` ロールを追加：

```diff
 export type Message = {
-  role: 'user' | 'assistant' | 'url';
+  role: 'user' | 'assistant' | 'url' | 'image';
   content: MessageContent[];
 };
```

### 5. `frontend/src/components/ChatInterface.tsx`

#### bgcolor に image ロールの色を追加

```diff
-bgcolor: message.role === 'user' ? '#e3f2fd' : message.role === 'url' ? '#e8f5e9' : '#f5f5f5',
+bgcolor: message.role === 'user' ? '#e3f2fd' : message.role === 'url' ? '#e8f5e9' : message.role === 'image' ? '#fff3e0' : '#f5f5f5',
```

#### image ロールの表示コンポーネント追加（url ロールの後、assistant ロールの前）

```tsx
) : message.role === 'image' ? (
  <Box>
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
      Chart
    </Typography>
    <Box
      component="img"
      src={getMessageContent(message)}
      alt="Chart"
      sx={{
        maxWidth: '100%',
        height: 'auto',
        borderRadius: 1,
        cursor: 'pointer'
      }}
      onClick={() => window.open(getMessageContent(message), '_blank')}
    />
  </Box>
) : (
```

#### Assistant メッセージ内の markdown 画像にも max-width を適用

Assistant の Box sx に以下を追加：
```tsx
'& img': {
  maxWidth: '100%',
  height: 'auto',
  borderRadius: 1
},
```

### 6. `lib/webbackend.ts`

#### 環境変数に CODE_INTERPRETER_REGION を追加

```diff
 const envs: any = {
   SESSION_TABLE: this.sessionTable.tableName,
   ...
   ATHENA_WORKGROUP: 'primary',
+  CODE_INTERPRETER_REGION: 'us-west-2'
 };
```

#### CodeInterpreter 用 IAM ポリシーを追加（athenaPolicy の後）

```typescript
const codeInterpreterPolicy = new iam.PolicyStatement({
  actions: [
    'bedrock-agentcore:CreateCodeInterpreter',
    'bedrock-agentcore:StartCodeInterpreterSession',
    'bedrock-agentcore:InvokeCodeInterpreter',
    'bedrock-agentcore:StopCodeInterpreterSession',
    'bedrock-agentcore:DeleteCodeInterpreter',
    'bedrock-agentcore:ListCodeInterpreters',
    'bedrock-agentcore:GetCodeInterpreter',
    'bedrock-agentcore:GetCodeInterpreterSession',
    'bedrock-agentcore:ListCodeInterpreterSessions'
  ],
  resources: ['*']
});
this.agentProcessor.addToRolePolicy(codeInterpreterPolicy);
```

---

## デプロイ手順

```bash
# 1. npm install
npm install

# 2. デプロイ
npx cdk deploy --all --require-approval never

# 3. テストデータ生成・アップロード
cd dbloader
python3 gen_testdata.py
# upload_to_s3.py の S3_BUCKET_NAME をデプロイ出力の DataBucketOutput の値に設定
python3 upload_to_s3.py

# 4. Cognito ユーザー作成
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username testuser \
  --temporary-password 'TempPass1!' \
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password \
  --user-pool-id <UserPoolId> \
  --username testuser \
  --password 'TestUser1!' \
  --permanent
```

## 技術的なポイント

- `strands_tools.code_interpreter` の `AgentCoreCodeInterpreter` は画像をテキストとしてしか返さないため、`boto3` で `bedrock-agentcore` クライアントを直接使用
- CodeInterpreter の `executeCode` は Jupyter カーネルベースで動作し、`print()` の出力が `structuredContent.stdout` に入らないケースがある。最後の式の評価結果として画像データを返す方式で解決
- matplotlib の `plt.show()` をモンキーパッチして、`show()` 呼び出し時に画像をキャプチャ。さらにコード末尾でも残存 figure をキャプチャ
- CodeInterpreter サンドボックスに日本語フォントがないため、グラフのラベルは英語で出力し、テキスト応答で日本語の説明を付ける
