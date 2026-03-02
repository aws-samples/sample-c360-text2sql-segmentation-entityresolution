---
inclusion: manual
---

# AGENT_INSTRUCTION 更新ワークフロー

## 概要

`workshop/2-ai-bpr/solution/solution.md` の内容に基づいて、`lambda/webbackend/agent_processor.py` の `AGENT_INSTRUCTION` を更新し、再デプロイする。

## 前提条件

- `csv-to-glue-workflow` が完了済みであること
- `workshop/2-ai-bpr/solution/solution.md` が存在すること

## ワークフロー

### 1. solution.md を読み込む

`workshop/2-ai-bpr/solution/solution.md` を読み、ソリューションの概要・役割・振る舞いを把握する。

### 2. AGENT_INSTRUCTION を更新

`lambda/webbackend/agent_processor.py` の `AGENT_INSTRUCTION` に以下を追記する：

- `Your primary role is to:` セクションに、solution.md で定義されたエージェントとしての役割を追記
- `When a user asks a question about data, follow this process:` セクションに、ソリューションに沿った振る舞いを追記

注意：
- 既存の指示は削除・修正しない（追記のみ）
- SQL アシスタントとしての基本機能は維持する

### 3. cdk deploy で再デプロイ

```bash
npx cdk deploy --require-approval never
```
