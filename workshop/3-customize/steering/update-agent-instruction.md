---
inclusion: manual
---

# AGENT_INSTRUCTION 更新ワークフロー

## 概要

`workshop/2-ai-bpr/build/build.md` の内容に基づいて、`lambda/webbackend/agent_processor.py` の `AGENT_INSTRUCTION` を更新し、再デプロイする。

## 前提条件

- `csv-to-glue-workflow` が完了済みであること
- `workshop/2-ai-bpr/build/build.md` が存在すること

## ワークフロー

### 1. build.md を読み込む

`workshop/2-ai-bpr/build/build.md` を読み、AI エージェントのプロトタイプ設計（対象 Shift シナリオ、エージェントの役割・振る舞い）を把握する。

### 2. AGENT_INSTRUCTION を更新

`lambda/webbackend/agent_processor.py` の `AGENT_INSTRUCTION` に以下を追記する：

- `Your primary role is to:` セクションに、build.md で定義された AI エージェントとしての役割を追記
- `When a user asks a question about data, follow this process:` セクションに、build.md の Shift シナリオに沿った振る舞いを追記

注意：
- 既存の指示は削除・修正しない（追記のみ）
- SQL アシスタントとしての基本機能は維持する

### 3. cdk deploy で再デプロイ

デプロイ前に Docker が利用可能か確認してください：

```bash
docker info > /dev/null 2>&1 && echo "OK" || echo "NG"
```

`NG` の場合、まず docker グループにユーザーを追加してください：

```bash
sudo usermod -aG docker $USER
sudo systemctl restart docker
```

その後、`sg` コマンドで docker グループ権限を使ってデプロイを実行してください：

```bash
sg docker -c "npx cdk deploy --require-approval never"
```

Docker が利用可能（`OK`）な場合はそのまま実行してください：

```bash
npx cdk deploy --require-approval never
```
