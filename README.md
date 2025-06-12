# AMT Customer 360 サンプルプロジェクト

## 概要

このプロジェクトは、AWS Entity Resolution を活用して異なるデータソース間で顧客データを照合・統合し、自然言語による対話でセグメントを作成することができる、Customer 360 を始めるためのサンプル実装です。Amazon Personalize item-affinity recipe によるセグメンテーション機能にも対応しています。

## 動作イメージ
![demo](docs/imgs/demo.gif)


## 想定ユースケース
デフォルトでは、メインブランドとサブブランドの 2 つの自社ECサイトを運用している事業者が持つデータを使って、ワークフローが実行されます。ワークフローでは、はじめに 2つの EC サイトで重複している顧客情報が AWS Entity Resolution の ML を用いたマッチングにより統合された後に、Amazon Personalize によってユーザーが好みそうな商品の推薦を生成します。その後、チャットインターフェイスを通じてセグメンテーション（条件に合致するユーザーの抽出）や、属性・購買行動の分析を行うことができます。例えば、以下のような質問文を与えると、分析結果を得られます。
* “メインブランドとサブブランドの両方で2回以上購買経験がある顧客がメインブランドで買っている商品のトップ3をおしえて”
* “その3つのアイテムいずれかを購入しそうな顧客のリストをください。ただし、すでに購入した実績のある顧客は除外して“
* “顧客のリストをCSVで出力して”


## ソリューションが提供する価値
デジタルやリアル店舗、自社データと他社データなど、ブランドと顧客のタッチポイントから得られるデータは多様化しています。不揃いなデータを統合すること、また膨大なデータからインサイトを得ることは、より良い顧客体験創出のために重要であることは理解されつつも、取り組めていないという企業も多数存在します。このサンプルソリューションでは、データ、システム、組織の課題に対して解決策を提供し、企業がデータを活用して顧客体験を向上させる取り組みを後押しします。


## Architecture

![arch](docs/imgs/architecture.drawio.png)


## デプロイ方法


1. クレデンシャルの設定

AWS のクレデンシャルを作業ターミナルで設定してください

2. Bedrock モデルアクセス許可

[AWS マネジメントコンソール](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess)から、Anthropic Claude 3.7 Sonnet を有効化してください （リージョン us-east-1, us-east-2, us-west-2 全てで行ってください)

3. 依存関係をインストール
```bash
npm ci
```

4. CDK bootstrap（初回のみ）
```bash
npm run cdk bootstrap
```

5. デプロイ実行
```bash
npm run cdk -- deploy --all
```

6. 完了

完了時、表示される Outputs から下記二つの値をメモしてください
- `AmtC360MarketingStack.DataStorageDataBucketOutput`
- `AmtC360MarketingStack.WebAppUrl`


## テストデータ準備

1. テストデータ生成

下記のようにスクリプトを実行し、テスト用CSVを作成してください

```bash
python dbloader/gen_testdata.py
```

2. テストデータアップロードスクリプト編集

`dbloader/upload_to_s3.py` をテキストエディタで開き、S3_BUCKET_NAME 変数に、デプロイ時にメモしたバケット名を設定してください

3. テストデータアップロード

アップロードを実行してください

```bash 
python dbloader/upload_to_s3.py
```

4. データ統合ワークフロー実行

AWS Entity Resolution / Amazon Personalize によるデータ統合ワークフローを実行します。
[AWS Step Functions のマネジメントコンソール](https://ap-northeast-1.console.aws.amazon.com/states/home?region=ap-northeast-1#/statemachines)を開いて `DataIntegrationWorkflow`で始まる StateMachine を実行してください


## ユーザ作成

Amazon Cognito User Pool でユーザを作成します。
[マネジメントコンソール](https://ap-northeast-1.console.aws.amazon.com/cognito/v2/idp/user-pools?region=ap-northeast-1) から、ユーザを作成してください。

以上で準備が完了です。
デプロイ時にメモした `AmtC360MarketingStack.WebAppUrl`のURLにブラウザからアクセスしてください