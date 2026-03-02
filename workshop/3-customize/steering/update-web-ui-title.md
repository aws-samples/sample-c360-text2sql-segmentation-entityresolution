---
inclusion: manual
---

# WEB UI タイトル更新ワークフロー

## 概要

`workshop/2-ai-bpr/solution/solution.md` の内容に基づいて、WEB UI のアプリ名を変更する。

## 前提条件

- `workshop/2-ai-bpr/solution/solution.md` が存在すること

## ワークフロー

### 1. solution.md を読み込む

`workshop/2-ai-bpr/solution/solution.md` を読み、ソリューションにふさわしいアプリ名を決定する。

### 2. WEB UI タイトルを更新

以下の2箇所の「C360 AI Chat Assistant」を新しい名前に置き換える：

- `frontend/index.html` - `<title>` タグ
- `frontend/src/pages/Main.tsx` - AppBar 内の Typography

### 3. cdk deploy で再デプロイ

```bash
npx cdk deploy --require-approval never
```
