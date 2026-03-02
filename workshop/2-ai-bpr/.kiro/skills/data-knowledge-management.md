# data/ ナレッジ管理スキル

`data/` フォルダに格納されたファイルを `data/knowledge/` にナレッジとして登録・管理し、回答時に適切なリファレンスとして活用するためのスキルです。

---

## このスキルの使い方

### いつ使うか

以下の場合にこのスキルを参照してください:

- `data/` に新しいファイルが追加された時
- ユーザーから「ナレッジに登録して」「data/のファイルを取り込んで」等の指示を受けた時
- ユーザーの質問に回答する際、`data/knowledge/` に関連するリファレンスがないか確認したい時
- 「このデータについて教えて」「〇〇の情報を調べて」等の質問を受けた時

### 何を提供するか

1. `data/` のファイルを `data/knowledge/` にMarkdown形式またはpickle形式で変換・保存
2. `data/knowledge/list.txt` による登録済みファイルの管理（重複防止・更新管理）
3. grepSearch等による回答時のリファレンス検索

---

## 2. ナレッジ登録の手順

### 2.1 事前確認

1. `.gitkeep` は無視する（ナレッジ登録の対象外）
2. ワークスペースの絶対パスを取得する（PDF等のバイナリ変換で `file://` URIが必要なため）:
   ```powershell
   Get-Item "data" | Select-Object FullName
   ```
   - 取得したパスを以降の処理で使用する（例: `C:\Users\Documents\codes\ai-bpr\data\`）
   - 相対パスやユーザー名の推測は絶対にしないこと
3. `data/knowledge/list.txt` を確認し、対象ファイルが登録済みか確認する
4. 登録済みの場合、元ファイルの更新日付と `list.txt` の記録日付を比較する
5. 更新日付が新しい場合のみ再登録する

### 2.2 ファイル種別ごとの処理

#### Markdownファイル（.md）

元からMarkdown形式のファイルはそのまま `data/knowledge/{元ファイル名}` としてコピーする（変換不要）。
冒頭にメタデータのfront-matterが無い場合のみ追加する:

```markdown
---
source: data/example.md
registered: 2026-02-17
---

（元の内容をそのまま保持）
```

#### その他テキスト系ファイル（.txt, .json, .yaml, .yml, .xml, .html 等）

1. ファイル内容を読み取る
2. Markdown形式に変換して `data/knowledge/{元ファイル名}.md` として保存
3. 元のファイル構造・見出し・リストを可能な限り保持する
4. メタデータ（元ファイルパス、変換日時）をMarkdownの冒頭に記載する

Markdown冒頭のメタデータ形式:
```markdown
---
source: data/example.txt
converted: 2026-02-17
---

# example.txt

（変換された内容）
```

#### CSV/TSV/Excel等の表形式ファイル（.csv, .tsv, .xlsx, .xls 等）

1. まずpandasで読み込みを試みる:
   ```python
   import pandas as pd
   df = pd.read_csv("data/example.csv")  # or read_excel, read_table等
   ```
2. 正常に読み込めた場合:
   - pickle形式で `data/knowledge/{元ファイル名}.pkl` として保存
   - 同時に、データの概要（カラム名、行数、先頭数行のサンプル、基本統計量）をMarkdown形式で `data/knowledge/{元ファイル名}.md` として保存
3. 読み込みに失敗した場合:
   - テキストとして読み取り、Markdown形式で保存する

概要Markdownの形式:
```markdown
---
source: data/example.csv
converted: 2026-02-17
format: pickle
pickle_path: data/knowledge/example.csv.pkl
---

# example.csv

## 概要
- 行数: 1000
- カラム数: 5
- カラム: id, name, value, category, date

## サンプルデータ（先頭5行）

| id | name | value | category | date |
|----|------|-------|----------|------|
| 1  | AAA  | 100   | X        | 2025-01-01 |
| ...| ...  | ...   | ...      | ... |

## 基本統計量

（df.describe()の結果）
```

#### PDF等のバイナリファイル

1. 事前確認で取得したワークスペース絶対パスを使って `file://` URIを組み立てる:
   - 例: `file:///C:/Users/Documents/codes/workshop/2-ai-bpr/data/令和6年度計算書類.pdf`
   - Windowsの場合、バックスラッシュをスラッシュに変換し、先頭に `file:///` を付ける
2. markitdownツール（`mcp_markitdown_convert_to_markdown`）を使用してMarkdownに変換する
2. 変換結果を `data/knowledge/{元ファイル名}.md` として保存する
3. 変換に失敗した場合はその旨を `list.txt` に記録する

#### 画像ファイル（.png, .jpg, .gif 等）

1. ファイル名と格納パスのみを記録する
2. Markdownファイルにはファイルパスへの参照を記載する

### 2.3 list.txt の更新

登録完了後、`data/knowledge/list.txt` を更新する。

list.txtの形式:
```
# data/knowledge 登録一覧
# 形式: 元ファイルパス | knowledge保存パス | 登録日時 | ステータス | 概要
data/example.csv | data/knowledge/example.csv.md, data/knowledge/example.csv.pkl | 2026-02-17 | OK | 売上データ（1000行×5カラム: id, name, value, category, date）
data/report.pdf | data/knowledge/report.pdf.md | 2026-02-17 | OK | 2025年度Q3の営業レポート。成約率・失注分析を含む
data/meeting.md | data/knowledge/meeting.md | 2026-02-17 | OK | 2026-02-10のプロジェクト定例会議メモ。次回アクション3件
data/broken.csv | - | 2026-02-17 | FAILED: pandas読み込みエラー | -
```

概要の書き方:
- ファイルの内容を1行（50文字程度）で要約する
- CSVなどの表形式は行数・カラム名を含める
- ドキュメント系はテーマ・主要トピックを含める
- FAILEDの場合は `-` とする
- この概要により、`list.txt` を見るだけで目的のナレッジを素早く特定できる

---

## 3. ナレッジの活用（回答時の検索）

### 3.1 リファレンス検索の手順

ユーザーの質問に回答する際:

1. `data/knowledge/list.txt` を確認し、関連しそうなナレッジがあるか確認
2. 関連するMarkdownファイルに対して `grepSearch` で検索:
   ```
   grepSearch(query="検索キーワード", includePattern="data/knowledge/**/*.md")
   ```
3. 必要に応じてMarkdownファイルの該当箇所を `readFile` で読み取る
4. pickleファイルがある場合、pandasで読み込んで分析:
   ```python
   import pandas as pd
   df = pd.read_pickle("data/knowledge/example.csv.pkl")
   ```

### 3.2 回答時の引用

ナレッジを参照して回答する場合、出典を明示する:
```
（参照: data/example.csv より）
```

---

## 4. ディレクトリ構成

```
data/
├── .gitkeep
├── example.csv          # 元ファイル（ユーザーが配置）
├── report.pdf           # 元ファイル
└── knowledge/
    ├── list.txt          # 登録一覧（重複・更新管理）
    ├── example.csv.md    # CSV概要（Markdown）
    ├── example.csv.pkl   # CSVデータ（pickle）
    └── report.pdf.md     # PDF変換（Markdown）
```

---

## 5. ナレッジの削除（元ファイル削除時）

元ファイルが `data/` から削除された場合、対応するナレッジも削除する。

### 5.1 削除手順

1. `data/knowledge/list.txt` から該当エントリを特定する
2. 対応する `data/knowledge/` 内のファイル（.md, .pkl 等）をすべて削除する
3. `list.txt` から該当行を削除する

### 5.2 一括整合チェック

`data/` 内のファイルと `list.txt` を突き合わせ、元ファイルが存在しないエントリを検出・削除する:

1. `list.txt` の各エントリについて、元ファイルパスの存在を確認
2. 元ファイルが存在しない場合、対応するknowledgeファイルを削除し、`list.txt` から行を削除

---

## 6. 注意事項

- `data/knowledge/` 内のファイルは自動生成物。元ファイルが正とする
- pickle形式はPythonバージョン依存があるため、環境が変わった場合は再生成が必要
- 大きなファイル（100MB超）はpickle保存を避け、概要Markdownのみ作成する
- `list.txt` は手動編集しない。スキルの手順に従って更新する
- `.gitkeep` は処理対象に含めない（無視する）
- `data/knowledge/` ディレクトリ自体や `list.txt` は削除しない

---

## 7. 実行例

```
ユーザー: 「data/にsales.csvを置いたので取り込んで」

あなた:
1. data/sales.csv を確認
2. data/knowledge/list.txt を確認（未登録を確認）
3. pandasでCSVを読み込み
4. data/knowledge/sales.csv.pkl として保存
5. data/knowledge/sales.csv.md に概要を保存
6. data/knowledge/list.txt を更新
7. 「sales.csvをナレッジに登録しました。1000行×5カラムのデータです。」と報告
```

```
ユーザー: 「売上トップ3の商品は？」

あなた:
1. data/knowledge/list.txt を確認
2. sales.csv.pkl があることを確認
3. pandasで読み込み、売上でソートしてトップ3を抽出
4. 結果を回答（参照: data/sales.csv より）
```

```
ユーザー: 「data/sales.csvを削除したよ」

あなた:
1. data/knowledge/list.txt を確認
2. sales.csv のエントリを特定
3. data/knowledge/sales.csv.md と data/knowledge/sales.csv.pkl を削除
4. list.txt から該当行を削除
5. 「sales.csv のナレッジを削除しました。」と報告
```
