# 技術記事収集機能

## 概要

本システムは、複数のRSS/Atomフィードから当日（もしくは設定に応じた過去数日）の技術記事を収集し、以下の処理を自動化する

- OpenAI APIを用いた記事本文の技術用語抽出
- 収集済み記事・用語の重複排除
- 抽出した用語に対する説明生成とNotion登録（バッチ処理）
- 記事一覧メールの自動配信
- CloudWatch Logsへの監査用ログ出力

Lambda上で定期実行するサーバーレス構成を想定しており、設定値やテンプレートはS3上のファイルとSecrets Managerから動的に読み込む

## 機能

- **フィード収集**: `feed_sources.json` に定義されたメディア／URLを基に、RSSとAtomの双方に対応して記事を取得する
- **記事フィルタリング**: 設定されたタイムゾーンを基準に、収集対象日の記事のみを抽出する。設定で、収集する日数を指定可能
- **技術用語抽出**: OpenAI APIを利用して記事本文から技術用語を抽出する
- **重複排除**: 記事URLおよび技術用語の正規化キーをDynamoDBに保存し、再収集・重複投稿を防ぐ
- **Notion連携**: 抽出した技術用語に自動で説明を生成しNotionデータベースへ登録する
- **メール配信**: あらかじめ設定されたHTMLテンプレートを用いて記事一覧メールを構築し、SESで送信する
- **監査ログ**: CloudWatch Logsへ収集結果（成功・失敗）を所定のフォーマットで記録する

## 構成図

## 依存サービス

- **AWS Lambda**: メインの実行環境
- **Amazon S3**: 設定／テンプレートファイルの保管
- **AWS Secrets Manager**: APIキーやメールアドレス等の機密情報保管
- **Amazon DynamoDB**: 収集済み記事URL・技術用語の重複排除
- **Amazon SES**: メール配信
- **Amazon CloudWatch Logs**: 監査ログ出力
- **Notion**: 技術用語データベースの更新
- **OpenAI(ChatGPT)**: 記事要約・技術用語抽出

## 実行フロー

実行するLambda関数は２つ
- 記事を収集し、OpenAI APIで技術用語を抽出し、DynamoDBに収集した記事と技術用語を登録する(メイン処理)
- DynamoDBに登録されている技術用語の説明をOpenAI APIに生成させ、Notionデータベースに用語を登録する(バッチ処理)

これらは別のタイミングで実行される

### メイン処理

1. Lambda実行時に環境変数を読み込み、S3から設定ファイルを取得
2. Secrets ManagerからOpenAI APIのトークン/メールアドレスをロード
3. 各フィードからRSS/Atomを取得し、対象日の記事のみ抽出。重複チェック後、DynamoDBへ書き込み
4. 記事本文をOpenAIに送信して用語抽出を実施。重複チェック後、DynamoDBへ書き込み
6. メールテンプレートを用いて記事一覧を作成し、SESで配信
7. CloudWatch Logsへ成功ログ（記事一覧・用語一覧）を出力。途中で例外が発生した場合はエラーログを出力して終了

### バッチ処理

1. Lambda実行時に環境変数を読み込み、S3から設定ファイルを取得
2. Secrets ManagerからOpenAI API／Notion APIのトークンをロード
3. DynamoDBからまだ説明が生成されていない技術用語を取得し、OpenAIへ送信して説明を生成させる
4. 説明を生成した単語をNotionデータベースに登録、登録した用語はDynamoDBのフラグを立てて管理

## 実行スケジュール

### メイン処理

毎日23:00に実行

### バッチ処理

毎日24:00に実行

## DynamoDBテーブル

本システムで使用するテーブルは２つ
- `articles_table`：この記事 URL をキーに保存し、再収集を防止する
- `terms_table`：正規化タームをキーに保存し、用語重複を排除する

テーブルの物理名、カラムの物理名は設定ファイルで指定する

### articles_table

カラム定義、カラム名はconfigファイルに定義されているキー名
|カラム名|型|説明|
|:------|:-|:---|
|article_attr|String|収集した記事のURL|
|created_at_attr|String|収集した日時。フォーマット、タイムゾーンは[DynamoDBへの書き込み](#DynamoDBへの書き込み)を参照|

一度収集した記事のURLを登録する
記事を収集する際に、このテーブルを使用して重複チェックを行う

### terms_table

カラム定義、カラム名はconfigファイルに定義されているキー名
|カラム名|型|説明|
|:------|:-|:---|
|term_attr|String|正規化された技術用語|
|original_attr|String|技術用語の原文|
|article_url_attr|String|この技術用語を最初に抽出した記事|
|is_described_attr|Bool|この技術用語がすでに説明を生成されていたらtrue|
|created_at_attr|String|登録した日時。フォーマット、タイムゾーンは[DynamoDBへの書き込み](#DynamoDBへの書き込み)を参照|
|updated_at_attr|String|更新した日時。フォーマット、タイムゾーンは[DynamoDBへの書き込み](#DynamoDBへの書き込み)を参照|

一度収集した技術用語を登録する
キー(term_attr)は正規化された技術用語であり、技術用語を収集した際に重複チェックに利用する
Notionに登録される技術用語はoriginal_attrに格納されている値である

## 詳細仕様

### 共通処理

#### DynamoDBへの書き込み
- 作成日時、更新日時はJSTで書き込む
- 作成日時、更新日時のyyyy-mm-dd HH:MM:ss

#### 環境変数
以下はLambdaの環境変数に設定される
- s3の設定ファイルが格納されているバケット名
- s3の設定ファイルパス

#### 設定
実行に必要な情報は設定ファイルから読み取る
設定ファイルの詳細は[config.json](#config.json)を参照

#### OpenAIへの問い合わせ

- マルチスレッドで動作させる、スレッド数は設定ファイルから読み込む
- 一度に用語を説明させる数の最大数は設定ファイルから読み込む
- 一回でOpenAIへ問い合わせる単語数は設定ファイルから読み込む

### メイン処理

#### メール本文のフォーマット
メール本文内の各記事の装飾は設定ファイルに記述
詳細は[mail_body_template_file.html](#mail_body_template_file.html)を参照

#### RSSフィードからの記事の収集
収集する記事一覧は、設定ファイルに記述
詳細は[feed_sources.json](#feed_sources.json)を参照

収集はマルチスレッドで行う
設定ファイルでスレッドの最大数を制御できる

#### 技術用語の正規化

収集した技術用語は比較する際に、表記揺れを回避するために正規化を行う
正規化の要件は以下である
- Unicode正規化
- case insensitive
- 空白を除去する

DynamoDBのterms_table.term_attrには正規化された用語を挿入する

### バッチ処理

- １回の実行で説明を生成される用語の数には上限を設ける、上限数は設定ファイルから読み込み
- ChatGPTに一度に問い合わせる単語数には上限を設ける、上限数は設定ファイルから読み込み
- タイムアウト対策でNotionへの書き込み数も上限を設ける、上限数は設定ファイルから読み込み
- Notionへの書き込みもマルチスレッドで行う、スレッド数は設定ファイルから読み込み

## Notionテーブル

|カラム名|説明|
|:------|:---|
|term_property|技術用語|
|description_property|技術用語の説明|

## ログ内容

CloudWatch Logs には以下の形式で情報を出力する
日付は収集対象日のタイムゾーンでフォーマットされる
出力するログレベルは環境変数で制御する

### 収集終了後ログ

記事の一覧を出力
```text
[INFO][収集日(yyy-mm-dd形式)] 収集した記事一覧
タイトル1 (url1)
タイトル2 (url2)
...
```

収集した技術用語の一覧を出力
```text
[INFO][収集日(yyy-mm-dd形式)] 収集した技術用語一覧
用語1
用語2
...
```

### エラーログ

次のフォーマットで出力
```text
[ERROR][収集日(yyy-mm-dd形式)] 収集に失敗
エラーの理由
```

エラー発生時は例外内容を「エラーの理由」に記載し、そのままスタックに伝播させる（再試行時にCloudWatchログでトレース可能）

## 設定ファイル一覧

- env.json
  - 環境変数を設定する
  - このファイルを元にAWS Lmabdaの環境変数を設定する
  - 主に他の設定ファイルのソースを定義するファイル

- config.json
  - プログラムの動作に関わる設定を記述する
  - このファイルはs3に配置される

- mail_body_template_file.html
  - メール本文に掲載する、１つの記事を表示するためのHTMLテンプレートを記述する
  - このファイルはs3に配置される

- feed_sources.json
  - 収集対象のRSSフィードを記載する
  - フィードは複数記載される
  - このファイルはs3に配置される
  
## 設定ファイル詳細

### env.json

```json
{
  "Variables": {
    "s3_bucket_name": "s3-backet-name",
    "config_file_name": "config.json",
    "mail_body_template_file_name": "mail_body_template_file.html",
    "feed_sources_file_name": "feed_sources.json",
    "log_level": "INFO"
  }
}
```

#### キー詳細

| キー | 必須 | 説明 |
|------------|------|------|
| `Variables.s3_bucket_name` | 必須 | 設定ファイルが置かれているs3バケット名 |
| `Variables.config_file_name` | 必須 | s3バケットに置かれているプログラムの動作に関わる設定ファイル名 |
| `Variables.mail_body_template_file_name` | 必須 | s3バケットに置かれているHTMLテンプレートが記述されているファイル名 |
| `Variables.feed_sources_file_name` | 必須 | s3バケットに置かれているRSSフィード一覧が記述されているファイル名 |
| `Variables.log_level` | 必須 | 出力するログレベル。このレベル以上のログが出力される |

### config.json

```json
{
  "aws": {
    "secrets_manager": {
      "secret_id": "secret_id",
      "region": "ap-northeast-1",
      "OpenAI_api_key": "OpenAI_api_key",
      "Notion_api_token_key": "Notion_api_token",
      "source_email_address_key": "source_email_addres",
      "destination_email_address_key": "destination_email_address"
    },
    "dynamodb": {
      "region": "ap-northeast-1",
      "articles_table_name": "rss_distributor_article",
      "terms_table_name": "rss_distributor_term",
      "article_attr": "source_url",
      "term_attr": "term",
      "original_attr": "original_term",
      "article_url_attr": "article_url",
      "is_described_attr": "is_described",
      "created_at_attr": "created_at",
      "updated_at_attr": "updated_at"
    },
    "ses": {
      "region": "ap-northeast-1",
      "subject_template": "技術記事一覧 {date:%Y年%m月%d日}号"
    },
    "cloudwatch": {
      "region": "ap-northeast-1",
      "log_group_name": "RSSDistribute"
    }
  },
  "processing": {
    "model": "gpt-4o-mini",
    "per_feed_limit": 5,
    "chunk_size": 3500,
    "temperature": 0.2,
    "collection_timezone": "Asia/Tokyo",
    "delay_seconds": 0.0,
    "collection_days": 2,
    "notion_batch_size": 50,
    "description_batch_size": 20,
    "description_fetch_limit": 200,
    "feed_max_workers": 4,
    "chatgpt_max_workers": 4,
    "notion_max_workers": 2,
  },
  "notion": {
    "database_id": "12345678-1234-1234-1234-123456789abc",
    "term_property": "Term",
    "description_property": "Description",
    "api_version": "2025-09-03"
  }
}
```

#### キー詳細

| キー | 必須 | 説明 |
|------------|------|------|
| `aws.*.region` | 任意 | awsリソースのリージョン。省略した場合はap-northeast-1 |
| `aws.secrets_manager.secret_id` | 必須 | Secrets Managerから取得する機密情報のid |
| `aws.secrets_manager.OpenAI_api_key` | 必須 | Secrets Managerに格納されているOpenAI API キー名 |
| `aws.secrets_manager.Notion_api_token_key` | 必須 | Secrets Managerに格納されているNotionのAPIトークン キー名 |
| `aws.secrets_manager.source_email_address_key` | 必須 | Secrets Managerに格納されている送信元メールアドレス キー名 |
| `aws.secrets_manager.destination_email_address_key` | 必須 | Secrets Managerに格納されている送信先メールアドレス キー名 |
| `aws.dynamodb.articles_table_name` | 必須 | 収集済みの記事のURLを格納するテーブル |
| `aws.dynamodb.terms_table_name` | 必須 | 収集済みの技術用語を格納するテーブル |
| `aws.dynamodb.article_attr` | 必須 | articles_tableのURLを格納するカラム名 |
| `aws.dynamodb.term_attr` | 必須 | terms_tableの正規化された用語を格納するカラム名 |
| `aws.dynamodb.original_attr` | 必須 | terms_tableの原文の用語を格納するカラム名 |
| `aws.dynamodb.article_url_attr` | 必須 | terms_tableの初めて用語を取得した記事のURLを格納するカラム名 |
| `aws.dynamodb.created_at_attr` | 必須 | terms_table、articles_tableのレコードが作成された時刻を格納するカラム。形式はyyyy-mm-dd HH:MM:ss |
| `aws.ses.subject_template` | 必須 | 送信するメールの件名のテンプレート。{date:format}となっている部分を収集当日の日付に置き換える、":"の右側は日付のフォーマット。dateのタイムゾーンはprocessing.collection_timezoneと合わせる |
| `aws.cloudwatch.log_group_name` | 必須 | ログを出力するロググループ名 |
| `processing.model` | 必須 | ChatGPTのモデル名 |
| `processing.per_feed_limit` | 必須 | 1フィードあたりの最大取得件数 |
| `processing.chunk_size` | 必須 | ChatGPTにわたす記事を分割した際の、チャンクあたりの最大文字数 |
| `processing.temperature` | 必須 | ChatGPTの生成される選択の調整。0～1の範囲で指定。1に近いほど正確性が落ちて創造性が増す |
| `processing.collection_timezone` | 必須 | 収集対象とするタイムゾーン |
| `processing.delay_seconds` | 必須 | API呼び出しの遅延秒数 |
| `processing.collection_days` | 必須 | 当日を含めて過去何日分を収集するか |
| `processing.notion_batch_size` | 任意 | Notionへ登録する際の1バッチあたりの件数 |
| `processing.description_batch_size` | 任意 | 用語説明をChatGPTへ問い合わせる際の最大件数 |
| `processing.description_fetch_limit` | 任意 | DynamoDBから一度に取得する未説明用語の上限 |
| `processing.feed_max_workers` | 必須 | 記事を収集するときの最大スレッド数 |
| `processing.chatgpt_max_workers` | 必須 | ChatGPTへの問い合わせの最大スレッド数 | 
| `processing.notion_max_workers` | 必須 | NotionAPIへの問い合わせの最大スレッド数 |
| `processing.notion_timeout_seconds` | 任意 | Notion API 呼び出しのタイムアウト秒数（既定 10 秒） |
| `notion.database_id` | 必須 | 技術用語を格納するNotionのデータベースID |
| `notion.term_property` | 必須 | Notionデータベースの技術用語を格納するカラム名 |
| `notion.description_property` | 必須 | Notionデータベースの技術用語の説明を格納するカラム名 |
| `notion.api_version` | 必須 | Notion APIのバージョン |

### mail_body_template_file.html

メール本文に掲載する、１つの記事を表示するためのHTMLテンプレートを記述する
変数を記述できるようにしているので、プログラムで変換する
変数は{}で囲われている

#### 変数
| 変数名 | 変換内容 |
|------------|------|
| url | 記事のURL |
| media | 記事が掲載されているメディア |
| title | 記事のタイトル |

### feed_sources.json

```json
{
  "articles": [
    {
      "media_name": "media_name1",
      "url": "https[:]//media1/abc"
    },
    {
      "media_name": "media_name2",
      "url": "https[:]//media2/abc"
    }
  ]
}
```

#### キー詳細

| キー | 必須 | 説明 |
|------------|------|------|
| `media_name` | 必須 | RSSフィードのメディア名。zennなど |
| `url` | 必須 | RSSフィードのURL |
