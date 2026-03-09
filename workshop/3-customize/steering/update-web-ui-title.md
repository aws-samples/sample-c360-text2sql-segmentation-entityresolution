---
inclusion: manual
---

# WEB UI タイトル更新ワークフロー

## 概要

`workshop/2-ai-bpr/build/build.md` の内容に基づいて、WEB UI のアプリ名を変更する。

## 前提条件

- `workshop/2-ai-bpr/build/build.md` が存在すること

## ワークフロー

### 0. スタック名の確認

`bin/amt-c360-marketing.ts` を読み、デプロイ時のスタック名を確認してください。1-deploy で prefix が付与されている場合、`AmtC360MarketingStack` ではなく `<PREFIX>_AmtC360MarketingStack` のようになっています。以降の cdk deploy ではこのスタック名が使用されます。

### 1. build.md を読み込む

`workshop/2-ai-bpr/build/build.md` を読み、AI エージェントのプロトタイプ設計に基づいてソリューションにふさわしいアプリ名を決定する。

### 2. WEB UI タイトルを更新

以下の2箇所の「C360 AI Chat Assistant」を新しい名前に置き換える：

- `frontend/index.html` - `<title>` タグ
- `frontend/src/pages/Main.tsx` - AppBar 内の Typography

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
