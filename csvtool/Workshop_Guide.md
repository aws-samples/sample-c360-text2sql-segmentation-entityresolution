# Workshop_Guide

### リンク

One-Click（Customer 360 Data Fusion / C360DF）：

<https://aws-samples.github.io/sample-one-click-generative-ai-solutions/solutions/c360/>

### １、デプロイ手順

#### １−１、AWSアカウントのコンソールにログイン

a.  どのリージョンにもC360をデプロイしていないこと

#### １−２、下記のURLの1 click で AWS のソリューションがデプロイできる solution box の Customer 360 Data Fusion のページからデプロイ

URL：<https://aws-samples.github.io/sample-one-click-generative-ai-solutions/solutions/c360/>

画面イメージ：

![](./media/ITI8202ebb05c2d46c28fd31b1b4.png)

#### １−３、スタックのクイック作成

NotificationEmailAddress　に　受信可能なメールアドレスを設定する。他の項目はデフォルトのままにする。

![](./media/ITI874b65f425de4742b4c72b3ec.png)

#### １−４、スタックの作成を押す

![](./media/ITI5a809eda80a841ca8138220cb.png)

#### １−５、デプロイ完了まで待つ（おおよそ30分）

b.  デプロイ開始直後に AWS Notification - Subscription Confirmation
    というタイトルのメールが送られてくるから \"Confirm subscription\"
    をクリックしておくこと

##### １−５−１、途中、C360 Deployment Started というタイトルのメールが送られてくるが特に何もしなくていい

![](./media/ITI85f95a5103a7457ca15acb693.png)

##### １−５−２、タイミングが遅過ぎてConfirm subscriptionをすると、デプロイの通知が来ない場合がある。

a.  その場合は、AWS
    コンソールのスタック画面で確認する　（はじめてのデプロイの場合、スタック[CDKToolkit](https://docs.aws.amazon.com/ja_jp/cdk/v2/guide/bootstrapping.html)もデプロイされる）

通知メール：

![](./media/ITIaf687d49742c4264a41605ea1.png)

##### １−５−３、AWS コンソールのスタック画面：

One-Click Deploy で東京を選んだ場合:

<https://ap-northeast-1.console.aws.amazon.com/cloudformation/home> からアクセスできる。

![](./media/ITIda078f8dab724d57bdceeb953.png)

*ここで全員のデプロイが終わるまで待つ*

### ２、デプロイ後の確認

#### **２−１、フロントエンドURL**

One-Click Deploy で東京を選んだ場合:

<https://ap-northeast-1.console.aws.amazon.com/cloudformation/home> から下記の項目をメモする

![](./media/ITI7789030df1cf48259a559fd93.png)

### **３、テストデータ（CSV形式）をS3バケットにアップロードする**

#### **３−１、CloudShellを起動する**

![](./media/ITI7210ee049718439d85b47a7e0.png)

![](./media/ITI58b32b4e72764484b5abab51c.png)

![](./media/ITIea7aee0bf2af4c569db6f7ebd.png)

#### **３−２、C360をCloneする**

git clone
https://github.com/aws-samples/sample-c360-text2sql-segmentation-entityresolution.git

![](./media/ITI5d42817e631546e8b47eda1f7.png)

#### ３−３、テストデータ生成

cd sample-c360-text2sql-segmentation-entityresolution/\
\
python dbloader/gen_testdata.py

![](./media/ITId4dae94b84ad48a9a8e77360e.png)

#### **３−４、自分の環境に合わせて、S3のバケット名をメモする**

##### **３−４−１、S3のバケット名を特定する**

 スタックAmtC360MarketingStackの出力画面で特定する

![](./media/ITI5fdb7c3cfd2540b2ade3fef1c.png)

##### ３−４−２、自分の環境のS3バケット名に書き換える

テキストエディタで書き換えて、確認してから実行してください。

![](./media/ITIa934c00eb3964728b176ecab5.png)

sed -i \'s/\<set bucket name
here\>/ここにスタック出力結果からコピーしたバケット名/g\' ./dbloader/upload_to_s3.py

##### ３−４−３、テストデータをアップロードする

python dbloader/upload_to_s3.py

![](./media/ITIb3de3b5792914a25afb57be4b.png)

##### ３−４−４、S3、Glue、Athenaで確認する

- S3バケットでアップロードされたCSVファイルを確認する

![](./media/ITI50fa78f7ec6342ec9824ab190.png)

- Glue Catalogで登録情報を確認する

![](./media/ITI85f95a5103a7457lmvgjwe9893.png)

**Table overview**

![](./media/ITI7aa0b3a24e444a448cd1a6779.png)

- Athenaクエリ実行とそのための設定

![](./media/ITIf1fcca6354e64701a9ccf0d94.png)

![](./media/ITI269b47301b6c467babee4d8ab.png)

![](./media/ITI8f9ecc966c7942cb8813a6c80.png)

![](./media/ITI7e899e5a5a724c528a34f9484.png)

＊　"athenaresults' を含むように検索すると特定できる。

![](./media/ITIe75f703cafb94cc2a9a8543a2.png)

![](./media/ITIa5a52dd39ab9409a9cb8ce27c.png)

![](./media/ITIeb6d860e462143cb889932122.png)

#### ３−５、テストデータに自然言語で質問してみる

##### ３−５−１、Amazon Cognito User Pool でユーザ作成する

![](./media/ITIc98665aa948e42beb3cdd3b88.png)

![](./media/ITI2ea61872ad3b4834812daa824.png)

![](./media/ITI1b2b728e07e84c0bab32a8599.png)

フロントエンドURLを取得する

One-Click Deploy で東京を選んだ場合:

<https://ap-northeast-1.console.aws.amazon.com/cloudformation/home> から下記の項目をメモする

![](./media/ITI9efdddc73f95456cb5be2c6b2.png)

設定したUsernameとPasswordでSign inする

![](./media/ITI256dd20cf11946c29c164d91e.png)

Passwordを変更する

![](./media/ITI74a42b870ff54d61a563fb298.png)

ログイン後の画面が表示される

＊一度質問しておけば、DisconnectedからConnectedに変わります。

![](./media/ITIaa0e621eb887421f81412f791.png)

質問してみよう！

例：

顧客のリストをCSVで出力して

メインブランドの売上 TOP 3を教えて

使ったSQLを出してもらい、Athenaで実行してみる

SQLをAthena画面で実行して、出力した回答が正しいことをチェックできる。

![](./media/ITI9a7b449eadc24c858584df6f5.png)

### ４、自社CSVデータをアップロードする

#### **４−１、CSVデータをアップロードして、CSVToolのディレクトリに移動する**

![](./media/ITI55abe65ee98e4ebf863dd0f3d.png)

MACのファイル設定例（複数ファイルの場合、手順３を繰り返し実施する）

![](./media/ITI1e794d92063447778046c5337.png)

アップロードの結果はCloudShellの右下に表示される：

![](./media/ITI42a89c3068ae41c9aab5a6f7d.png)

CSVデータをCSVToolのディレクトリに移動する

複数のCSVをアップロードする際に、Too Many Requestsエラーになることがあります。その際にリトライしてください。

mv \~/\*.csv
/home/cloudshell-user/sample-c360-text2sql-segmentation-entityresolution/csvtool/csvfiles/

CSVデータが所定の場所に移動したかどうかを確認する。

ls -la
/home/cloudshell-user/sample-c360-text2sql-segmentation-entityresolution/csvtool/csvfiles/

![](./media/ITI2c2eb9ee2a804f66b2f554981.png)

#### ４−２、CSVデータを取り込む

**自分の環境に合わせて、自分の環境のデータをメモする**

##### ４−２−１、S3のバケット名

スタックAmtC360MarketingStackの出力画面で特定する

![](./media/ITI6e6bc45723a24aa0914e08045.png)

##### **４−２−２、Glue database 名**

Glueサービスの画面から特定する

amtc360marketingstackdatastoragegluedb12345678

![](./media/ITI162d06e6ac644bdda35aafad7.png)

##### ４−２−３、自分の環境のS3バケット名とGlue Database名を書き換える

テキストエディタで書き換えて、確認してから実行してください。

![](./media/ITIff486c589a68417f840cd388b.png)

sed -i
\'s/\<ここを実際のGlueデータベース名に置き換えてください\>/ここに４−２−２のGlue
database名/g\' ./csv_to_glue_catalog.py\
sed -i
\'s/\<ここを実際のs3バケット名に置き換えてください\>/ここに４−２−１のS3のバケット名/g\'
./csv_to_glue_catalog.py

##### ４−２−４、実行する

python3 -m venv venv

![](./media/ITI0c9bfb5b7f184e84a800d6174.png)

source venv/bin/activate && pip install -r requirements.txt

![](./media/ITIc6cab545d03e473d99d85671b.png)

python csv_to_glue_catalog.py

![](./media/ITI480abed40ab24da898467c1bc.png)

### 動作確認

スタックAmtC360MarketingStackの出力のWebAppUrlをクリックしてログインする。

![](./media/ITIda79c314752d42a48bdd073e7.png)

無事ログインできたら、めでたし、めでたし、アップしたCSVデータに自然言語で質問して探索を楽しんでください。

## Appendix

対象ソリューション：

sample-c360-text2sql-segmentation-entityresolution（略称：c360）

<https://github.com/aws-samples/sample-c360-text2sql-segmentation-entityresolution/tree/main>
