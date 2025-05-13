import os
import json
import re
import arxiv
import openai
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
from datetime import datetime

# .env の読み込み
load_dotenv()

# 設定ファイルのパス（従来の設定ファイルのみ使用）
CONFIG_FILE = "config.json"

# 設定ファイルを読み込む関数
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tags": ["AI", "generative AI"]}  # デフォルト値

# 設定の読み込み
config = load_config()
TAGS = config["tags"]

SLACK_TOKEN = os.getenv("SLACK_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_CHANNELS = os.getenv("SLACK_CHANNELS", "")
SLACK_CHANNEL_ID = None
ENABLE_NOTION = os.getenv("ENABLE_NOTION", "false").lower() == "true"

if not SLACK_TOKEN:
    raise ValueError("SLACK_TOKEN environment variable must be set.")

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY is not set. "
          "Translation and summarization features will be disabled.")

# OpenAI APIの設定（v0.27.8向け）
openai.api_key = OPENAI_API_KEY

# 単一チャンネルIDの取得
if SLACK_CHANNELS:
    pairs = SLACK_CHANNELS.split(",")
    for pair in pairs:
        parts = pair.split(":")
        if len(parts) == 2:
            key, channel_id = parts
            if key.strip() == "all" or len(pairs) == 1:
                SLACK_CHANNEL_ID = channel_id.strip()
                break

if not SLACK_CHANNEL_ID:
    print("Warning: No valid Slack channel ID found. "
          "Please set SLACK_CHANNELS environment variable.")

# Slack クライアントの作成
client = WebClient(token=SLACK_TOKEN)

# arXiv から論文を取得する関数
def fetch_arxiv_papers(tags):
    all_papers = {}

    for tag in tags:
        try:
            # 日付フィルタなしで、最新の論文を取得
            query = f"cat:{tag}"
            
            search = arxiv.Search(
                query=query,
                max_results=3,  # 各カテゴリで最大3件取得
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            papers = list(search.results())
            formatted_papers = []
            
            for paper in papers:
                # 論文情報を整形
                paper_info = {
                    "id": paper.get_short_id(),
                    "title": paper.title,
                    "url": paper.entry_id,
                    "authors": ", ".join([author.name for author in paper.authors]),
                    "published": paper.published.strftime("%Y-%m-%d"),
                    "summary": paper.summary,
                    "pdf_url": paper.pdf_url,
                    "tag": tag  # タグ情報を追加
                }
                formatted_papers.append(paper_info)
            
            all_papers[tag] = formatted_papers
            # デバッグ出力を追加
            print(f"Found {len(formatted_papers)} papers for category {tag}")
        except Exception as e:
            print(f"Error fetching papers for tag {tag}: {e}")
            all_papers[tag] = []
    
    return all_papers

# OpenAI APIを使って論文を翻訳・要約する関数
def translate_and_summarize_paper(paper):
    if not OPENAI_API_KEY:
        return {
            "translated_title": paper["title"],
            "translated_summary": "OpenAI API key is not set. Translation unavailable.",
            "key_qa": "OpenAI API key is not set. Key Q&A unavailable."
        }
    
    try:
        # プロンプトを作成
        prompt = f"""You are a summarization assistant. Given an academic paper content, generate a title, a concise summary, and a set of key Q&A that capture the essential points.

Paper Title: {paper['title']}
Authors: {paper['authors']}
Published: {paper['published']}

Abstract:
{paper['summary']}

Please provide:
1. Japanese title translation
2. Japanese summary in 400-600 characters
3. 3-5 key Q&A pairs that highlight the important aspects of this paper in Japanese
"""

        # UTF-8でエンコードしたテキストのみを使用
        safe_prompt = prompt.encode('utf-8', errors='ignore').decode('utf-8')
        
        # システムプロンプトも同様に処理
        system_prompt = "You are a research assistant who specializes in translating and summarizing academic papers from English to Japanese."
        safe_system_prompt = system_prompt.encode('utf-8', errors='ignore').decode('utf-8')
        
        # OpenAI APIを呼び出し（v0.27.8向け）
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # GPT-4の代わりにGPT-3.5-turboを使用
            messages=[
                {"role": "system", "content": safe_system_prompt},
                {"role": "user", "content": safe_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        # レスポンスから結果を取得（v0.27.8向け）
        result = response['choices'][0]['message']['content']
        
        # 結果を解析（シンプルに3つのセクションに分割）
        sections = result.split("\n\n", 2)
        
        if len(sections) >= 3:
            translated_title = sections[0].replace("Japanese title translation: ", "").strip()
            translated_summary = sections[1].replace("Japanese summary: ", "").strip()
            key_qa = sections[2].strip()
        else:
            translated_title = paper["title"]
            translated_summary = "要約の生成に失敗しました。"
            key_qa = "重要なQ&Aの生成に失敗しました。"
        
        return {
            "translated_title": translated_title,
            "translated_summary": translated_summary,
            "key_qa": key_qa
        }
    except Exception as e:
        print(f"Error translating and summarizing paper: {e}")
        return {
            "translated_title": paper["title"],
            "translated_summary": f"翻訳・要約中にエラーが発生しました: {str(e)}",
            "key_qa": "重要なQ&Aは利用できません。"
        }

# Slack にメッセージを送信する関数
def send_message_to_slack(channel_id, paper, thread_ts=None):
    # 論文情報を直接使用
    # text フィールドも付与（フォールバック用）
    text_fallback = f"{paper['title']} - {paper['url']}"
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📝 *論文タイトル:* {paper['title']}\n"
                        f"🏷️ *カテゴリ:* {paper['tag']}\n"
                        f"👨‍🔬 *著者:* {paper['authors']}\n"
                        f"📅 *公開日:* {paper['published']}\n"
                        f"🔗 *URL:* {paper['url']}\n"
                        f"📄 *PDF:* {paper['pdf_url']}\n\n"
                        f"📚 *要約:* \n{paper['summary'][:500]}...\n\n"
            }
        }
    ]
    
    try:
        response = client.chat_postMessage(
            channel=channel_id,
            text=text_fallback,
            blocks=blocks,
            thread_ts=thread_ts
        )
        print(f"Message sent: {response['ts']}")
        return response['ts']
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
        return None

# Slack チャンネル内で最新の親投稿のスレッドから、投稿された論文のURLを抽出する関数
def get_latest_parent_paper_urls(channel_id):
    try:
        # チャンネルの直近20件のメッセージを取得
        result = client.conversations_history(channel=channel_id, limit=20)
        messages = result.get('messages', [])
        # 親投稿（スレッドの開始投稿）で、「最新のarXiv論文」というテキストが含まれるものを抽出
        parent_messages = [
            m for m in messages 
            if ("📢 *最新のarXiv論文" in m.get('text', ''))
            and (("thread_ts" not in m) or (m.get('thread_ts') == m.get('ts')))
        ]
        if not parent_messages:
            return set()
        # 最新の親投稿（最も新しいもの）を選ぶ
        parent_messages.sort(key=lambda m: float(m['ts']), reverse=True)
        target_message = parent_messages[0]
        
        # 対象の親投稿のスレッド（返信）を取得。親投稿自体は除外する
        replies_result = client.conversations_replies(
            channel=channel_id,
            ts=target_message['ts'],
            limit=10
        )
        replies = replies_result.get('messages', [])
        paper_urls = []
        for msg in replies:
            if msg.get('ts') == target_message['ts']:
                continue  # 親投稿は除外
            text = msg.get('text', '')
            # 論文のURLを抽出（フォーマット例："🔗 *URL:* http://arxiv.org/..."）
            # 正規表現パターンを柔軟にして、URL部分を確実に捕捉できるようにする
            match = re.search(r"URL:.*?http[s]?://(?:arxiv\.org|[a-zA-Z0-9.-]+)/[^\s\">]+", text)
            if match:
                # URL部分だけを抽出
                url_text = match.group(0)
                url = re.search(r'http[s]?://[^\s">]+', url_text).group(0)
                paper_urls.append(url)
        
        print(f"Found {len(paper_urls)} existing paper URLs in the latest thread")
        return set(paper_urls)
    except SlackApiError as e:
        print(f"Error fetching latest parent message: {e.response['error']}")
        return set()

# Slackコマンドでタグを更新する関数
def update_tags(new_tags):
    global TAGS
    TAGS = new_tags
    config = {"tags": new_tags}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    return TAGS

# arXiv論文をSlackに通知する関数
def notify_papers_to_slack():
    if not SLACK_CHANNEL_ID:
        print("❌ Error: Slack channel ID is not set.")
        return
        
    papers_by_tag = fetch_arxiv_papers(TAGS)
    
    # 今日の記事が見つかったかどうか
    has_papers = any(len(papers) > 0 for papers in papers_by_tag.values())
    
    if not has_papers:
        print("No papers found for any tag.")
        return
    
    # 最新の親投稿から投稿された論文のURLを取得
    latest_paper_urls = get_latest_parent_paper_urls(SLACK_CHANNEL_ID)
    
    # 今日の新規親投稿を作成し、スレッドを開始
    try:
        parent_response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"📢 *最新のarXiv論文 - {datetime.now().strftime('%Y-%m-%d')}*"
        )
        thread_ts = parent_response['ts']
        
        # すべてのタグの論文を1つのスレッドに投稿
        for tag, papers in papers_by_tag.items():
            for paper in papers:
                if paper["url"] in latest_paper_urls:
                    print(f"論文 {paper['id']} は既に通知済みです。スキップします。")
                    continue
                
                send_message_to_slack(
                    channel_id=SLACK_CHANNEL_ID,
                    paper=paper,
                    thread_ts=thread_ts
                )
            
    except SlackApiError as e:
        print(f"Error sending parent message: {e.response['error']}")

if __name__ == "__main__":
    notify_papers_to_slack()
