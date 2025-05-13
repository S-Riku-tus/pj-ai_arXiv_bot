# arXiv Slack Bot

このプロジェクトは、arXivから特定のカテゴリの最新論文を定期的にSlackに通知するボットです。
優先順位の高いカテゴリから最も価値のある1つの論文を選び、AI（OpenAIまたはGemini）を使用して日本語に翻訳・要約します。

## インストール

以下のコマンドで依存ライブラリをインストールできます。

```bash
pip install -r requirements.txt
```

## 環境設定

以下の環境変数を `.env` ファイルに設定する必要があります：

```
# Slackトークン（必須）
SLACK_TOKEN=xoxb-your-slack-token

# 通知先チャンネル（必須）
SLACK_CHANNELS=all:C12345678

# 選択するAIサービス: "openai" または "gemini"（デフォルトはopenai）
AI_SERVICE=openai

# OpenAI APIキー（AI_SERVICE=openaiの場合に必要）
OPENAI_API_KEY=your-openai-api-key

# Gemini APIキー（AI_SERVICE=geminiの場合に必要）
GEMINI_API_KEY=your-gemini-api-key

# Notion連携（オプション）
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

### カテゴリの優先順位

configファイル内のタグの順序が優先順位を表します。例えば、デフォルト設定の場合：

```json
{
    "tags": ["cs.AI", "cs.LG", "cs.CL"]
}
```

この設定では、cs.AIが最も優先度が高く、次にcs.LG、最後にcs.CLとなります。
ボットは各カテゴリから最新の1つの論文を取得し、優先度の高いものから順に選択して1つの論文だけを通知します。

### APIキーの設定

#### OpenAI API
1. [OpenAI Platform](https://platform.openai.com/)からアカウントを作成し、APIキーを取得
2. 取得したAPIキーを`.env`ファイルの`OPENAI_API_KEY`に設定
3. `AI_SERVICE=openai`に設定

#### Gemini API
1. [Google AI Studio](https://makersuite.google.com/app/apikey)からAPIキーを取得
2. 取得したAPIキーを`.env`ファイルの`GEMINI_API_KEY`に設定
3. `AI_SERVICE=gemini`に設定

## 使い方

```bash
python bot.py
```

実行すると、設定したカテゴリの最新arXiv論文を優先順位に従って1つだけSlackに通知します。論文のタイトル、著者、要約が日本語に翻訳され、重要なポイントがQ&A形式で提供されます。

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

### 定期実行の設定

以下のようにcronを設定して、毎朝自動実行することができます：

```
0 8 * * * cd /path/to/project && python bot.py
```
