# arXiv Slack Bot

このプロジェクトは、arXivから特定のカテゴリの最新論文を定期的にSlackに通知するボットです。
OpenAIのAPIを使用して、論文の翻訳と要約を行い、日本語で通知します。

## インストール

以下のコマンドで依存ライブラリをインストールできます。

```bash
pip install -r requirements.txt
```

## 環境設定

以下の環境変数を `.env` ファイルに設定する必要があります：

```
SLACK_TOKEN=xoxb-your-slack-token
OPENAI_API_KEY=your-openai-api-key
SLACK_CHANNELS=cs.AI:C12345678,cs.LG:C87654321

# Notion連携のための設定（オプション）
ENABLE_NOTION=false
```

### arXivのカテゴリについて

arXivの主なカテゴリには以下のようなものがあります：

- `cs.AI` - 人工知能
- `cs.CL` - 計算言語学と自然言語処理
- `cs.CV` - コンピュータビジョンとパターン認識
- `cs.LG` - 機械学習
- `cs.NE` - ニューラルネットワーク
- `cs.RO` - ロボティクス

完全なリストは[arXivのカテゴリ一覧](https://arxiv.org/category_taxonomy)を参照してください。

### OpenAI APIの設定

1. [OpenAI Platform](https://platform.openai.com/)からアカウントを作成し、APIキーを取得
2. 取得したAPIキーを`.env`ファイルの`OPENAI_API_KEY`に設定

## 使い方

```bash
python bot.py
```

実行すると、設定したカテゴリの最新arXiv論文をSlackに通知します。論文のタイトル、著者、要約が日本語に翻訳され、重要なポイントがQ&A形式で提供されます。

### Slackコマンドの設定

Slackのスラッシュコマンドを設定して、通知するarXivのカテゴリを変更できます。

1. [Slack API](https://api.slack.com/apps)から新しいアプリを作成
2. 「Slash Commands」を有効にし、`/set_tags`コマンドを追加
3. Request URLを`https://あなたのサーバー/slack/set_tags`に設定
4. Flaskサーバーを起動：`python slack_commands.py`

コマンドの使用例:
```
/set_tags cs.AI, cs.CL, cs.CV
```
