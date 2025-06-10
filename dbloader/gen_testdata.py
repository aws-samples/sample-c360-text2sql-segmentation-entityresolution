import random
import uuid
from datetime import datetime, timedelta
import os
import argparse

# Test data settings
num_customers = 1000
num_items = 500
num_purchases = 3000

# Sub-brand data settings
num_subbrand_customers = 1000  # Number of sub-brand customers
num_subbrand_items = 200  # Number of sub-brand items (40% of main)
num_subbrand_purchases = 900  # Number of sub-brand purchases (30% of main)

# Percentage of customers to be identified as the same person
similar_customer_ratio = 0.5  # 50% of customers exist in both brands
# Percentage of customers with purchase experience in both brands (part of similar_customer_ratio)
cross_purchase_ratio = 0.3  # 30% of customers have purchase experience in both brands

# 名前のサンプルデータ（ローマ字のみ、バリエーション大幅増加）
first_names = [
    # 日本の名前（ローマ字）
    "Taro",
    "Hanako",
    "Ichiro",
    "Naoko",
    "Kenta",
    "Mika",
    "Shota",
    "Keiko",
    "Daisuke",
    "Yuko",
    "Akira",
    "Yuki",
    "Takeshi",
    "Emi",
    "Hiroshi",
    "Ayumi",
    "Kazuki",
    "Sakura",
    "Ryo",
    "Natsumi",
    "Satoshi",
    "Yui",
    "Takuya",
    "Aya",
    "Makoto",
    "Haruka",
    "Daiki",
    "Misaki",
    "Tatsuya",
    "Nanami",
    "Sho",
    "Aoi",
    "Yamato",
    "Yuna",
    "Hayato",
    "Rin",
    "Koki",
    "Hina",
    "Sota",
    "Momoka",
    "Ryota",
    "Miyu",
    "Yuta",
    "Saki",
    "Kaito",
    "Ayaka",
    "Haruki",
    "Risa",
    "Kosuke",
    "Mao",
    # 英語圏の名前
    "John",
    "Mary",
    "James",
    "Patricia",
    "Robert",
    "Jennifer",
    "Michael",
    "Linda",
    "William",
    "Elizabeth",
    "David",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Christopher",
    "Nancy",
    "Daniel",
    "Lisa",
    "Matthew",
    "Betty",
    "Anthony",
    "Margaret",
    "Mark",
    "Sandra",
    "Donald",
    "Ashley",
    "Steven",
    "Kimberly",
    "Paul",
    "Emily",
    "Andrew",
    "Donna",
    "Joshua",
    "Michelle",
    "Kenneth",
    "Dorothy",
    "Kevin",
    "Carol",
    "Brian",
    "Amanda",
    "George",
    "Melissa",
    "Edward",
    "Deborah",
    # その他の国際的な名前
    "Carlos",
    "Maria",
    "Juan",
    "Sofia",
    "Luis",
    "Isabella",
    "Miguel",
    "Valentina",
    "Alejandro",
    "Camila",
    "Wei",
    "Xiu",
    "Jie",
    "Min",
    "Hao",
    "Yan",
    "Chen",
    "Hui",
    "Lei",
    "Na",
    "Ali",
    "Fatima",
    "Mohammed",
    "Aisha",
    "Ahmed",
    "Zainab",
    "Omar",
    "Layla",
    "Hassan",
    "Noor",
    "Raj",
    "Priya",
    "Amit",
    "Neha",
    "Vikram",
    "Anjali",
    "Arjun",
    "Pooja",
    "Rahul",
    "Meera",
    "Ivan",
    "Olga",
    "Sergei",
    "Natasha",
    "Dmitri",
    "Anastasia",
    "Vladimir",
    "Svetlana",
    "Nikolai",
    "Ekaterina",
]

last_names = [
    # 日本の姓（ローマ字）
    "Sato",
    "Suzuki",
    "Takahashi",
    "Tanaka",
    "Ito",
    "Watanabe",
    "Yamamoto",
    "Nakamura",
    "Kobayashi",
    "Kato",
    "Yoshida",
    "Yamada",
    "Sasaki",
    "Yamaguchi",
    "Matsumoto",
    "Inoue",
    "Kimura",
    "Hayashi",
    "Shimizu",
    "Saito",
    "Yamazaki",
    "Abe",
    "Mori",
    "Ikeda",
    "Hashimoto",
    "Ishikawa",
    "Ogawa",
    "Goto",
    "Okada",
    "Hasegawa",
    "Murakami",
    "Kondo",
    "Ishii",
    "Maeda",
    "Fujita",
    "Endo",
    "Aoki",
    "Sakamoto",
    "Ota",
    "Fujii",
    "Nishimura",
    "Fukuda",
    "Miura",
    "Takeuchi",
    "Nakajima",
    "Okamoto",
    "Matsuda",
    "Harada",
    "Nakagawa",
    "Nakano",
    # 英語圏の姓
    "Smith",
    "Johnson",
    "Williams",
    "Jones",
    "Brown",
    "Davis",
    "Miller",
    "Wilson",
    "Moore",
    "Taylor",
    "Anderson",
    "Thomas",
    "Jackson",
    "White",
    "Harris",
    "Martin",
    "Thompson",
    "Garcia",
    "Martinez",
    "Robinson",
    "Clark",
    "Rodriguez",
    "Lewis",
    "Lee",
    "Walker",
    "Hall",
    "Allen",
    "Young",
    "Hernandez",
    "King",
    "Wright",
    "Lopez",
    "Hill",
    "Scott",
    "Green",
    "Adams",
    "Baker",
    "Gonzalez",
    "Nelson",
    "Carter",
    "Mitchell",
    "Perez",
    "Roberts",
    "Turner",
    "Phillips",
    "Campbell",
    "Parker",
    "Evans",
    "Edwards",
    "Collins",
    # その他の国際的な姓
    "Gonzalez",
    "Rodriguez",
    "Fernandez",
    "Lopez",
    "Martinez",
    "Perez",
    "Sanchez",
    "Ramirez",
    "Torres",
    "Flores",
    "Wang",
    "Li",
    "Zhang",
    "Liu",
    "Chen",
    "Yang",
    "Huang",
    "Zhao",
    "Wu",
    "Zhou",
    "Kim",
    "Lee",
    "Park",
    "Choi",
    "Jung",
    "Kang",
    "Cho",
    "Yoon",
    "Jang",
    "Lim",
    "Singh",
    "Patel",
    "Sharma",
    "Kumar",
    "Shah",
    "Verma",
    "Rao",
    "Reddy",
    "Joshi",
    "Malhotra",
    "Ivanov",
    "Smirnov",
    "Kuznetsov",
    "Popov",
    "Sokolov",
    "Lebedev",
    "Kozlov",
    "Novikov",
    "Morozov",
    "Petrov",
]

# 商品名のサンプルデータ
# メインブランド（服の商品）
clothing_prefixes = ["エレガント", "カジュアル", "モダン", "ヴィンテージ", "プレミアム"]
clothing_types = [
    "シャツ",
    "スーツ",
    "ジャケット",
    "スカート",
    "ドレス",
    "パンツ",
    "ブラウス",
    "コート",
    "セーター",
    "カーディガン",
]
clothing_styles = [
    "フォーマル",
    "カジュアル",
    "ビジネス",
    "アウトドア",
    "スポーツ",
]

# サブブランド（アクセサリー商品）
accessory_prefixes = ["ラグジュアリー", "スタイリッシュ", "クラシック", "トレンディ", "ハンドクラフト"]
accessory_types = [
    "ピアス",
    "ネックレス",
    "指輪",
    "ブレスレット",
    "腕時計",
    "ヘアピン",
    "ブローチ",
    "アンクレット",
    "カフスボタン",
    "ティアラ",
]
accessory_styles = [
    "カジュアル",
    "フォーマル",
    "ウェディング",
    "パーティー",
    "デイリー",
]


def generate_dummy_data():
    """テストデータを生成する関数"""

    # 同姓同名の発生を制御するための辞書
    name_combinations = {}
    # メールアドレスの重複を防ぐための辞書
    email_addresses = {}

    # customer_master
    customer_master = []
    customer_data = []  # 顧客データを保持するリスト

    for i in range(num_customers):
        customer_id = str(uuid.uuid4())
        gender = random.choice(["male", "female", "unknown"])

        # 名前の選択（同姓同名が極端に多くならないように制御）
        if i < num_customers * 0.98:  # 98%は重複しない名前の組み合わせ
            while True:
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                name_key = f"{first_name}_{last_name}"

                # この名前の組み合わせがまだ使われていなければ採用
                if name_key not in name_combinations:
                    name_combinations[name_key] = 1
                    break
        else:
            # 残り2%は意図的に同姓同名を作る（年齢などで判別できるケース）
            existing_keys = list(name_combinations.keys())
            if existing_keys:
                name_key = random.choice(existing_keys)
                first_name, last_name = name_key.split("_")
                name_combinations[name_key] += 1
            else:
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)

        # メールアドレスの生成（同姓同名の場合は番号を付ける）
        base_email = f"{first_name.lower()}.{last_name.lower()}"
        if base_email in email_addresses:
            email_count = email_addresses[base_email] + 1
            email_addresses[base_email] = email_count
            email = f"{base_email}_{email_count}@example.com"
        else:
            email_addresses[base_email] = 1
            email = f"{base_email}@example.com"

        age = random.randint(18, 80)
        created_dt = datetime.now() - timedelta(days=random.randint(0, 365))
        created_at = int(created_dt.timestamp())  # Convert to Unix time in seconds

        customer_data.append(
            {
                "customer_id": customer_id,
                "email": email,
                "firstname": first_name,
                "lastname": last_name,
                "gender": gender,
                "age": age,
                "created_at": created_at,
            }
        )

        customer_master.append(f"{customer_id},{email},{first_name},{last_name},{gender},{age},{created_at}")

    # item_master - メインブランド専用の商品（服の商品）
    item_master = []
    for i in range(num_items):
        item_id = i + 1
        item_type = random.choice(clothing_types)
        item_name = f"{random.choice(clothing_prefixes)}{item_type} {random.randint(100, 999)}"
        price = random.randint(3000, 50000)
        item_category = item_type
        item_style = random.choice(clothing_styles)
        created_dt = datetime.now() - timedelta(days=random.randint(0, 365))
        created_at = int(created_dt.timestamp())
        item_master.append(f"{item_id},{item_name},{price},{item_category},{item_style},{created_at}")

    # purchase_history
    purchase_history = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    for _ in range(num_purchases):
        customer = random.choice(customer_data)
        item_id = random.randint(1, num_items)
        purchase_dt = start_date + timedelta(seconds=random.randint(0, int((end_date - start_date).total_seconds())))
        purchase_timestamp = int(purchase_dt.timestamp())  # Convert to Unix time in seconds
        purchase_history.append(f"{customer['customer_id']},{item_id},{purchase_timestamp}")

    # subbrand_customer_master - 約半数は同一人物っぽいデータ
    subbrand_customer_master = []
    subbrand_customer_data = []

    # 顧客データをシャッフル
    shuffled_customers = customer_data.copy()
    random.shuffle(shuffled_customers)

    # 同一人物と判定する顧客の割合に基づいて数を計算
    similar_count = int(num_customers * similar_customer_ratio)

    # サブブランドの顧客数を確保
    for i in range(num_subbrand_customers):
        # i がshuffled_customersの範囲内かチェック
        if i < len(shuffled_customers):
            customer = shuffled_customers[i]
        else:
            # 範囲外の場合はランダムに選択
            customer = random.choice(shuffled_customers)

        subbrand_id = str(uuid.uuid4())  # 新しいID

        if i < similar_count:
            # 同一人物のデータを生成（基本情報は同じ）
            email = customer["email"]
            first_name = customer["firstname"]
            last_name = customer["lastname"]
            gender = customer["gender"]
            age = customer["age"]
            created_dt = datetime.now() - timedelta(days=random.randint(0, 365))
            created_at = int(created_dt.timestamp())

            # 元データとの関連付けを記録（実際のデータには含まれない、分析用）
            related_to = customer["customer_id"]
        else:
            # 完全に新しいデータ
            gender = random.choice(["male", "female", "unknown"])
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"{first_name.lower()}.{last_name.lower()}.sub@example.com"
            age = random.randint(18, 80)
            created_dt = datetime.now() - timedelta(days=random.randint(0, 365))
            created_at = int(created_dt.timestamp())
            related_to = None

        subbrand_customer_data.append(
            {
                "customer_id": subbrand_id,
                "email": email,
                "firstname": first_name,
                "lastname": last_name,
                "gender": gender,
                "age": age,
                "created_at": created_at,
                "related_to": related_to,
            }
        )

        subbrand_customer_master.append(f"{subbrand_id},{email},{first_name},{last_name},{gender},{age},{created_at}")

    # subbrand_item_master - サブブランド専用の商品（アクセサリー商品）
    subbrand_item_master = []
    for i in range(num_subbrand_items):
        item_id = i + 1
        item_type = random.choice(accessory_types)
        item_name = f"{random.choice(accessory_prefixes)}{item_type} {random.randint(100, 999)}"
        price = random.randint(2000, 100000)
        item_category = item_type
        item_style = random.choice(accessory_styles)
        created_dt = datetime.now() - timedelta(days=random.randint(0, 365))
        created_at = int(created_dt.timestamp())
        subbrand_item_master.append(f"{item_id},{item_name},{price},{item_category},{item_style},{created_at}")

    # subbrand_purchase_history
    subbrand_purchase_history = []

    # 両方のブランドで購買経験のある顧客の数を計算
    cross_purchase_count = int(similar_count * cross_purchase_ratio)

    # 関連付けられた顧客（同一人物）のリスト
    related_customers = [c for c in subbrand_customer_data if c["related_to"]]

    # 両方のブランドで購入経験を持つ顧客を作成
    for i in range(min(cross_purchase_count, len(related_customers))):
        customer = related_customers[i]
        main_customer_id = customer["related_to"]

        # メインブランドでの購入履歴を確認
        main_purchases = [p for p in purchase_history if p.startswith(f"{main_customer_id},")]

        if main_purchases:
            # サブブランドでの購入を追加（1〜3件）
            for _ in range(random.randint(1, 3)):
                item_id = random.randint(1, num_subbrand_items)
                purchase_date = start_date + timedelta(seconds=random.randint(0, int((end_date - start_date).total_seconds())))
                purchase_timestamp = int(purchase_date.timestamp())
                subbrand_purchase_history.append(f"{customer['customer_id']},{item_id},{purchase_timestamp}")

    # 残りの購入履歴をランダムに生成
    remaining_purchases = num_subbrand_purchases - len(subbrand_purchase_history)
    for _ in range(remaining_purchases):
        customer = random.choice(subbrand_customer_data)
        item_id = random.randint(1, num_subbrand_items)
        purchase_date = start_date + timedelta(seconds=random.randint(0, int((end_date - start_date).total_seconds())))
        subbrand_purchase_timestamp = int(purchase_date.timestamp())
        subbrand_purchase_history.append(f"{customer['customer_id']},{item_id},{subbrand_purchase_timestamp}")

    # 分析用に関連データを出力
    relations = []
    for customer in subbrand_customer_data:
        if customer["related_to"]:
            relations.append(f"{customer['customer_id']},{customer['related_to']}")

    return {
        "customer_master": customer_master,
        "item_master": item_master,
        "purchase_history": purchase_history,
        "subbrand_customer_master": subbrand_customer_master,
        "subbrand_item_master": subbrand_item_master,
        "subbrand_purchase_history": subbrand_purchase_history,
        "customer_relations": relations,  # 分析用
    }


# データの生成と保存
def main():

    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description="Generate test data for Aurora database")
    parser.add_argument("--noheader", action="store_true", help="Exclude headers from CSV files (default: include headers)")
    args = parser.parse_args()

    # 出力ディレクトリの作成
    output_dir = "testdata"
    os.makedirs(output_dir, exist_ok=True)

    data = generate_dummy_data()

    # 同姓同名の別人をカウント
    main_name_count = {}
    sub_name_count = {}

    # メインブランドの同姓同名カウント
    for row in data["customer_master"]:
        parts = row.split(",")
        name_key = f"{parts[2]}_{parts[3]}"  # first_name + last_name
        if name_key in main_name_count:
            main_name_count[name_key] += 1
        else:
            main_name_count[name_key] = 1

    # サブブランドの同姓同名カウント
    for row in data["subbrand_customer_master"]:
        parts = row.split(",")
        name_key = f"{parts[2]}_{parts[3]}"  # first_name + last_name
        if name_key in sub_name_count:
            sub_name_count[name_key] += 1
        else:
            sub_name_count[name_key] = 1

    # 同姓同名の別人数をカウント
    main_duplicates = sum(1 for count in main_name_count.values() if count > 1)
    sub_duplicates = sum(1 for count in sub_name_count.values() if count > 1)

    # 同姓同名の人数（延べ人数 - ユニーク名前数）
    main_duplicate_persons = sum(count - 1 for count in main_name_count.values() if count > 1)
    sub_duplicate_persons = sum(count - 1 for count in sub_name_count.values() if count > 1)

    # テーブルごとのヘッダー定義
    headers = {
        "customer_master": "customer_id,email,firstname,lastname,gender,age,created_at",
        "item_master": "item_id,item_name,price,item_category,item_style,created_at",
        "purchase_history": "customer_id,item_id,purchase_date",
        "subbrand_customer_master": "customer_id,email,firstname,lastname,gender,age,created_at",
        "subbrand_item_master": "item_id,item_name,price,item_category,item_style,created_at",
        "subbrand_purchase_history": "customer_id,item_id,purchase_date",
        "customer_relations": "subbrand_customer_id,main_customer_id",
    }

    for table, rows in data.items():
        # ファイル拡張子をtsvからcsvに変更
        with open(f"{output_dir}/{table}.csv", "w") as f:
            # ヘッダーを書き込む（--noheaderオプションが指定されていない場合）
            if not args.noheader and table in headers:
                f.write(f"{headers[table]}\n")

            # データ行を書き込む
            for row in rows:
                f.write(f"{row}\n")

    print(f"テストデータの生成が完了しました。データは {output_dir} ディレクトリに保存されています。")
    print(f"ヘッダー出力: {'なし' if args.noheader else 'あり'}")
    print(f"メインブランド顧客数: {len(data['customer_master'])}")
    print(f"サブブランド顧客数: {len(data['subbrand_customer_master'])}")
    print(f"関連付けられた顧客数: {len(data['customer_relations'])}")
    print(f"両方のブランドで購買経験のある顧客数: {int(len(data['customer_relations']) * cross_purchase_ratio)}")
    print(f"メインブランドの同姓同名の種類数: {main_duplicates}")
    print(f"メインブランドの同姓同名の別人数: {main_duplicate_persons}")
    print(f"サブブランドの同姓同名の種類数: {sub_duplicates}")
    print(f"サブブランドの同姓同名の別人数: {sub_duplicate_persons}")


if __name__ == "__main__":
    main()
