from flask import Flask, request, jsonify
import json
import os
from dotenv import load_dotenv
from slack_sdk import WebClient
import subprocess

# .env を読み込む
load_dotenv()

app = Flask(__name__)
client = WebClient(token=os.getenv("SLACK_TOKEN"))
CONFIG_FILE = "config.json"


def commit_and_push_changes():
    """GitHub に `config.json` の変更を push する"""
    try:
        subprocess.run(["git", "config", "--global", "user.email", "bot@example.com"], check=True)
        subprocess.run(["git", "config", "--global", "user.name", "SlackBot"], check=True)
        subprocess.run(["git", "add", "config.json"], check=True)
        subprocess.run(["git", "commit", "-m", "Update config.json via Slack command"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ config.json を GitHub に push しました")
    except subprocess.CalledProcessError as e:
        print(f"❌ GitHub への push に失敗しました: {e}")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tags": ["cs.AI"]}


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


@app.route("/slack/set_tags", methods=["POST"])
def set_tags():
    data = request.form
    user_input = data.get("text", "").strip()

    if not user_input:
        return jsonify({"text": "⚠️ 設定するarXivカテゴリを指定してください！例: cs.AI, cs.CL, cs.CV"}), 200

    new_tags = [tag.strip() for tag in user_input.split(",")]
    config = load_config()
    config["tags"] = new_tags
    save_config(config)

    commit_and_push_changes()  # GitHub に変更を push

    response_text = f"✅ arXivカテゴリを更新しました！\n現在のカテゴリ: `{', '.join(new_tags)}`"
    return jsonify({"text": response_text}), 200


@app.route("/slack/help", methods=["POST"])
def help_command():
    help_text = """
*arXiv Slack Bot コマンド一覧*

`/set_tags cs.AI, cs.CL, cs.CV` - 通知するarXivカテゴリを設定します

*主要なarXivカテゴリ*
• `cs.AI` - 人工知能
• `cs.CL` - 計算言語学と自然言語処理
• `cs.CV` - コンピュータビジョンとパターン認識
• `cs.LG` - 機械学習
• `cs.NE` - ニューラルネットワーク
• `cs.RO` - ロボティクス

完全なリストは <https://arxiv.org/category_taxonomy|arXivのカテゴリ一覧> を参照してください。
"""
    return jsonify({"text": help_text}), 200


if __name__ == "__main__":
    app.run(port=5000)
