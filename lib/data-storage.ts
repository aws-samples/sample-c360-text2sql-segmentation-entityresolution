import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as glueAlpha from '@aws-cdk/aws-glue-alpha';
import { Construct } from 'constructs';

/**
 * Data Storage Layer Properties
 */
export interface DataStorageProps {}

/**
 * Data Storage Layer
 * Manages data storage resources such as S3 buckets, Glue database, and tables
 */
export class DataStorage extends Construct {
  public readonly dataBucket: s3.Bucket;
  public readonly athenaResultBucket: s3.Bucket;
  public readonly glueDatabase: glueAlpha.Database;
  public readonly customerMasterTable: glueAlpha.S3Table;
  public readonly subbrandCustomerMasterTable: glueAlpha.S3Table;
  public readonly integratedCustomerTable: glueAlpha.S3Table;
  public readonly integratedCustomerTablePrefix: string;
  public readonly itemMasterTable: glueAlpha.S3Table;
  public readonly subbrandItemMasterTable: glueAlpha.S3Table;
  public readonly purchaseHistoryTable: glueAlpha.S3Table;
  public readonly subbrandPurchaseHistoryTable: glueAlpha.S3Table;
  public readonly itemBasedSegmentTable: glueAlpha.S3Table;
  public readonly itemBasedSegmentPrefix: string;

  constructor(scope: Construct, id: string, props: DataStorageProps) {
    super(scope, id);

    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });
    new cdk.CfnOutput(this, 'DataBucketOutput', {
      value: this.dataBucket.bucketName
    });

    // S3 bucket for Athena query results
    this.athenaResultBucket = new s3.Bucket(this, 'AthenaResultsBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });

    this.glueDatabase = new glueAlpha.Database(this, 'GlueDB', {
      description: 'エンティティ解決と顧客360度分析のための顧客データ、商品情報、購入履歴を含むデータベース'
    });

    this.customerMasterTable = new glueAlpha.S3Table(this, 'CustomerMaster', {
      database: this.glueDatabase,
      tableName: 'customer_master',
      description: 'メインブランドの顧客マスターデータ。顧客の基本情報を含む',
      columns: [
        {
          name: 'customer_id',
          type: glueAlpha.Schema.STRING,
          comment: 'メインブランドシステムにおける顧客のID'
        },
        {
          name: 'email',
          type: glueAlpha.Schema.STRING,
          comment: '顧客のメールアドレス'
        },
        {
          name: 'firstname',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の名前'
        },
        {
          name: 'lastname',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の姓'
        },
        {
          name: 'gender',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の性別'
        },
        {
          name: 'age',
          type: glueAlpha.Schema.INTEGER,
          comment: '顧客の年齢（年単位）'
        },
        {
          name: 'created_at',
          type: glueAlpha.Schema.INTEGER,
          comment: '顧客レコードが作成されたUNIXタイムスタンプ'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: 'input/customer_master/'
    });

    this.subbrandCustomerMasterTable = new glueAlpha.S3Table(this, 'SubbrandCustomerMaster', {
      database: this.glueDatabase,
      tableName: 'subbrand_customer_master',
      description: 'サブブランドの顧客マスターデータ。メイン顧客マスターとマッチングして統合される',
      columns: [
        {
          name: 'customer_id',
          type: glueAlpha.Schema.STRING,
          comment: 'サブブランドシステムにおける顧客のID（メインブランドのcustomer_idとは別で、直接JOINできない）'
        },
        {
          name: 'email',
          type: glueAlpha.Schema.STRING,
          comment: '顧客のメールアドレス。'
        },
        {
          name: 'firstname',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の名前'
        },
        {
          name: 'lastname',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の姓'
        },
        {
          name: 'gender',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の性別'
        },
        {
          name: 'age',
          type: glueAlpha.Schema.INTEGER,
          comment: '顧客の年齢（年単位）'
        },
        {
          name: 'created_at',
          type: glueAlpha.Schema.INTEGER,
          comment: '顧客レコードが作成されたUNIXタイムスタンプ'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: 'input/subbrand_customer_master/'
    });

    this.integratedCustomerTablePrefix = 'integratedcustomer/latest';
    this.integratedCustomerTable = new glueAlpha.S3Table(this, 'IntegratedCustomer', {
      database: this.glueDatabase,
      tableName: 'integrated_customer',
      description: 'メインブランドとサブブランドの顧客レコード間のエンティティ解決から得られた統合顧客データ',
      columns: [
        {
          name: 'InputSourceARN',
          type: glueAlpha.Schema.STRING,
          comment:
            'この顧客レコードを提供したソーステーブルのARN。つまり、customer_masterテーブルとsubbrand_customer_masterテーブルのARN'
        },
        {
          name: 'ConfidenceLevel',
          type: glueAlpha.Schema.STRING,
          comment: 'マッチングの信頼性を示す信頼度スコア（0-1）'
        },
        {
          name: 'email',
          type: glueAlpha.Schema.STRING,
          comment: '顧客のメールアドレス'
        },
        {
          name: 'firstname',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の名前'
        },
        {
          name: 'lastname',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の姓'
        },
        {
          name: 'gender',
          type: glueAlpha.Schema.STRING,
          comment: '顧客の性別'
        },
        {
          name: 'age',
          type: glueAlpha.Schema.INTEGER,
          comment: '顧客の年齢'
        },
        {
          name: 'created_at',
          type: glueAlpha.Schema.INTEGER,
          comment: 'ソースシステムで顧客レコードが作成された元のUNIXタイムスタンプ'
        },
        {
          name: 'RecordId',
          type: glueAlpha.Schema.STRING,
          comment: 'ソースシステムからの元の顧客ID。それぞれのテーブルのcustomer_idとJOIN可能'
        },
        {
          name: 'MatchID',
          type: glueAlpha.Schema.STRING,
          comment: 'マッチしたレコードをグループ化するID。メインブランドとサブブランドで同じ顧客には同じ値となる'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: this.integratedCustomerTablePrefix
    });

    this.itemMasterTable = new glueAlpha.S3Table(this, 'ItemMaster', {
      database: this.glueDatabase,
      tableName: 'item_master',
      description: 'メインブランドの商品カタログ。商品の詳細と価格情報を含む。服を取り扱う',
      columns: [
        {
          name: 'item_id',
          type: glueAlpha.Schema.STRING,
          comment: 'メインブランドカタログ内の商品ID'
        },
        {
          name: 'item_name',
          type: glueAlpha.Schema.STRING,
          comment: '商品の名前/タイトル'
        },

        {
          name: 'price',
          type: glueAlpha.Schema.INTEGER,
          comment: '現地通貨での商品の現在価格'
        },
        {
          name: 'item_category',
          type: glueAlpha.Schema.STRING,
          comment: '商品のカテゴリ。「シャツ」や「スカート」など衣服の種類が入る'
        },
        {
          name: 'item_style',
          type: glueAlpha.Schema.STRING,
          comment: '商品のスタイル。「フォーマル」「カジュアル」などの文字列が入る'
        },
        {
          name: 'created_at',
          type: glueAlpha.Schema.INTEGER,
          comment: '商品がカタログに追加されたUNIXタイムスタンプ'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: 'input/item_master/'
    });

    this.subbrandItemMasterTable = new glueAlpha.S3Table(this, 'SubbrandItemMaster', {
      database: this.glueDatabase,
      tableName: 'subbrand_item_master',
      description: 'サブブランドの商品カタログ。商品の詳細と価格情報を含む',
      columns: [
        {
          name: 'item_id',
          type: glueAlpha.Schema.STRING,
          comment:
            'アクセサリを扱うサブブランドカタログ内の商品の商品ID（メインブランドのitem_masterのIDとは別体系なので直接JOINできない）'
        },
        {
          name: 'item_name',
          type: glueAlpha.Schema.STRING,
          comment: 'サブブランドの商品の名前/タイトル'
        },
        {
          name: 'price',
          type: glueAlpha.Schema.INTEGER,
          comment: 'サブブランドの商品の価格'
        },
        {
          name: 'item_category',
          type: glueAlpha.Schema.STRING,
          comment: 'サブブランドの商品のカテゴリ。「ピアス」や「ネックレス」などアクセサリの種類が入る'
        },
        {
          name: 'item_style',
          type: glueAlpha.Schema.STRING,
          comment: 'サブブランドの商品のスタイル。「パーティー」「カジュアル」などの文字列が入る'
        },
        {
          name: 'created_at',
          type: glueAlpha.Schema.INTEGER,
          comment: '商品がサブブランドカタログに追加されたUNIXタイムスタンプ'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: 'input/subbrand_item_master/'
    });

    this.purchaseHistoryTable = new glueAlpha.S3Table(this, 'PurchaseHistory', {
      database: this.glueDatabase,
      tableName: 'purchase_history',
      description: 'メインブランドからの顧客購入取引記録',
      columns: [
        {
          name: 'customer_id',
          type: glueAlpha.Schema.STRING,
          comment: '購入を行ったメインブランドシステムの顧客ID'
        },
        {
          name: 'item_id',
          type: glueAlpha.Schema.STRING,
          comment: '購入されたメインブランドカタログの商品ID'
        },
        {
          name: 'purchase_date',
          type: glueAlpha.Schema.INTEGER,
          comment: '購入取引が発生したUNIXタイムスタンプ'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: 'input/purchase_history/'
    });

    this.subbrandPurchaseHistoryTable = new glueAlpha.S3Table(this, 'SubbrandPurchaseHistory', {
      database: this.glueDatabase,
      tableName: 'subbrand_purchase_history',
      description: 'サブブランドからの顧客購入取引記録',
      columns: [
        {
          name: 'customer_id',
          type: glueAlpha.Schema.STRING,
          comment: '購入を行ったサブブランドシステムの顧客ID'
        },
        {
          name: 'item_id',
          type: glueAlpha.Schema.STRING,
          comment: '購入されたサブブランドカタログの商品ID'
        },
        {
          name: 'purchase_date',
          type: glueAlpha.Schema.INTEGER,
          comment: 'サブブランドシステムで購入取引が発生したUNIXタイムスタンプ'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: 'input/subbrand_purchase_history/'
    });

    this.itemBasedSegmentPrefix = 'item_based_segment/';
    this.itemBasedSegmentTable = new glueAlpha.S3Table(this, 'ItemBasedSegment', {
      database: this.glueDatabase,
      tableName: 'item_based_segment',
      description:
        'Personalizeバッチセグメントジョブから生成された顧客セグメント結果。特定のアイテムを購入しそうな顧客リストを得たい時にこのテーブルを参照する',
      columns: [
        {
          name: 'item_id',
          type: glueAlpha.Schema.STRING,
          comment: '商品ID。item_masterのitem_idとJOIN可能。'
        },
        {
          name: 'user_id',
          type: glueAlpha.Schema.STRING,
          comment: '顧客ID（MatchID）。integrated_customer_masterのMatchIDとJOIN可能'
        }
      ],
      parameters: { 'skip.header.line.count': '1' },
      dataFormat: glueAlpha.DataFormat.CSV,
      bucket: this.dataBucket,
      s3Prefix: this.itemBasedSegmentPrefix
    });
  }
}
