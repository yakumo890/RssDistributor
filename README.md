※ このREADMEは生成AI（ChatGPT）によって作成されています。

# RSS Distributor

RSS Distributor は、複数のRSS/Atomフィードから技術記事を自動収集し、要約・技術用語抽出・Notion登録・メール配信までを一貫して行うサーバーレスソリューションです。設定ファイルやテンプレートはS3上で管理するため、コードを再配置することなく運用パラメータを変更できます。

## 主な機能

- **フィード収集**: `feed_sources.json` に定義された複数メディア（RSS/Atom）を順次取得し、対象日の記事のみを抽出します。
- **用語抽出**: OpenAI Chat Completions API を利用し、記事本文から技術用語を抽出します。
- **重複排除**: 収集済みの記事URL・技術用語を DynamoDB に保存し、再処理を回避します。
- **Notion登録（バッチ）**: 未説明の技術用語を定期バッチで説明生成し、Notionデータベースへ登録します。
- **メール配信**: S3上のHTMLテンプレートを用いて記事一覧メールを作成し、SESで送信します。
- **ログ出力**: CloudWatch Logsに成功ログ（記事一覧・技術用語一覧）およびエラーログを記録します。

## リポジトリ構成

```
.
├── app.py                         # CDKアプリケーションのエントリーポイント
├── deploy.bash                    # デプロイ補助スクリプト
├── lambda/
│   ├── config/                    # 本番想定の設定ファイル（S3アップロード用）
│   ├── config/{dev,prod}/         # 環境別の設定ファイル
│   ├── main/                      # 記事収集Lambda（本体）
│   │   └── src/                   # メイン処理のPythonコード
│   └── batch/                     # 用語説明生成Lambda
│       └── src/                   # バッチ処理のPythonコード
├── rss_distributor/
│   └── rss_distributor_stack.py   # CDKスタック定義
├── specifications.md              # 仕様書と設定ファイルの詳細
└── requirements.txt など
```

## 必要な環境

- Python 3.12 以上
- Node.js および AWS CDK CLI v2 (`npm install -g aws-cdk`)
- AWSアカウント（Lambda / DynamoDB / SES / Secrets Manager / S3 / CloudWatch Logs の利用権限）
- SES で検証済みの送信元・送信先メールアドレス

## 初期セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 初回のみ: CDK環境のブートストラップ
cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
```

## 設定

1. `specifications.md` に従って S3 に以下のファイルを配置します。
   - `env.json` / `env_dev.json`（Lambda環境変数の元データ）
   - `config.json`、`feed_sources.json`、`mail_body_template_file.html`
2. Secrets Manager に以下を格納したシークレットを用意します。
   - OpenAI API キー
   - Notion API トークン
   - 送信元/送信先メールアドレス
3. `lambda/config/` や `lambda/config_dev/` を編集し、テーブル名やリージョン等を反映させます。

## デプロイ方法

```bash
# CloudFormationテンプレートの生成
cdk synth

# デフォルトアカウント／リージョンへデプロイ
cdk deploy

# スクリプトで一括実行する場合
./deploy.bash
```

## ローカル検証

- メイン処理: `cd lambda/main` で `uv run pytest`
- バッチ処理: `cd lambda/batch` で必要に応じてテストを追加実行
- SecretsやS3へのアクセスが必要な処理をローカル実行する場合は、AWS CLIの資格情報と環境変数を設定した上で `python -m src.summarize_zenn` などを実行してください。

## 運用上の注意

- Notionへの登録はバッチLambdaで実行されます。Notionデータベースのスキーマ（`Term` カラム等）を仕様書に合わせて整備してください。
- S3およびSecrets Managerの内容を更新することで、コードを変更せずに運用パラメータを調整できます。
- CloudWatch Logsには所定フォーマットでログが出力されるため、監視・トラブルシューティングに活用してください。
