import os
import json
import re
import arxiv
import openai
import google.generativeai as genai
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
    return {"tags": ["cs.AI", "cs.LG", "cs.CL"]}  # デフォルト値

# 設定の読み込み
config = load_config()
TAGS = config["tags"]

# タグの優先順位（配列の順番が優先順位を表す）
TAG_PRIORITY = TAGS.copy()  # 設定ファイルの順序をそのまま優先順位として使用

SLACK_TOKEN = os.getenv("SLACK_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_SERVICE = os.getenv("AI_SERVICE", "openai").lower()  # デフォルトはOpenAI
SLACK_CHANNELS = os.getenv("SLACK_CHANNELS", "")
SLACK_CHANNEL_ID = None
ENABLE_NOTION = os.getenv("ENABLE_NOTION", "false").lower() == "true"

if not SLACK_TOKEN:
    raise ValueError("SLACK_TOKEN environment variable must be set.")

# OpenAI APIの設定（v0.27.8向け）
if AI_SERVICE == "openai" and OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    print("Using OpenAI API for translation and summarization")
# Gemini APIの設定
elif AI_SERVICE == "gemini" and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("Using Gemini API for translation and summarization")
else:
    print("Warning: No valid AI API key set. Translation features will be disabled.")

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
    """各タグにつき1つずつ最新の論文を取得する"""
    all_papers = {}

    for tag in tags:
        try:
            # 日付フィルタなしで、最新の論文を取得（各タグ1件のみ）
            query = f"cat:{tag}"
            
            search = arxiv.Search(
                query=query,
                max_results=1,  # 各カテゴリで最大1件取得
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
def translate_and_summarize_paper_openai(paper):
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
        print(f"Error translating and summarizing paper with OpenAI: {e}")
        return {
            "translated_title": paper["title"],
            "translated_summary": f"翻訳・要約中にエラーが発生しました: {str(e)}",
            "key_qa": "重要なQ&Aは利用できません。"
        }

# Gemini APIを使って論文を翻訳・要約する関数
def translate_and_summarize_paper_gemini(paper):
    if not GEMINI_API_KEY:
        return {
            "translated_title": paper["title"],
            "translated_summary": "Gemini API key is not set. Translation unavailable.",
            "key_qa": "Gemini API key is not set. Key Q&A unavailable."
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

        # Gemini APIを呼び出し
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = model.generate_content(prompt)
        
        # レスポンスから結果を取得
        result = response.text
        
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
        print(f"Error translating and summarizing paper with Gemini: {e}")
        return {
            "translated_title": paper["title"],
            "translated_summary": f"翻訳・要約中にエラーが発生しました: {str(e)}",
            "key_qa": "重要なQ&Aは利用できません。"
        }

# 適切なAIサービスを使って論文を翻訳・要約する関数
def translate_and_summarize_paper(paper):
    if AI_SERVICE == "gemini" and GEMINI_API_KEY:
        return translate_and_summarize_paper_gemini(paper)
    elif AI_SERVICE == "openai" and OPENAI_API_KEY:
        return translate_and_summarize_paper_openai(paper)
    else:
        # 翻訳機能が利用できない場合は元の情報を返す
        return {
            "translated_title": paper["title"],
            "translated_summary": paper["summary"][:500] + "...",
            "key_qa": "AI translation service is not available."
        }

# Slack にメッセージを送信する関数
def send_message_to_slack(channel_id, paper, thread_ts=None):
    # 論文の翻訳・要約を取得
    try:
        translation = translate_and_summarize_paper(paper)
        
        # text フィールドも付与（フォールバック用）
        text_fallback = f"{translation['translated_title']} - {paper['url']}"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"【タイトル\n{translation['translated_title']}"
                            f"【title\n{paper['title']}"
                            f"【公開日\n{paper['published']}"
                            f"【URL\n{paper['url']}"
                            f"【重要なポイント】\n{translation['key_qa']}"
                            f"【要約】\n{translation['translated_summary']}"
                }
            }
        ]
    except Exception as e:
        print(f"Error preparing message: {e}")
        # エラーが発生した場合は元の論文情報のみを表示
        text_fallback = f"{paper['title']} - {paper['url']}"
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"【タイトル\n{translation['translated_title']}"
                            f"【title\n{paper['title']}"
                            f"【公開日\n{paper['published']}"
                            f"【URL\n{paper['url']}"
                            f"【要約】\n{translation['translated_summary']}"
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

# 優先度に基づいて最適な論文を選択する関数
def select_best_paper(papers_by_tag, tag_priority):
    """
    優先順位の高いカテゴリから順に論文を探し、最も優先度の高い論文を返す
    
    Args:
        papers_by_tag (dict): タグごとの論文リスト
        tag_priority (list): タグの優先順位（高い順）
    
    Returns:
        dict or None: 最適な論文、なければNone
    """
    for tag in tag_priority:
        if tag in papers_by_tag and papers_by_tag[tag]:
            return papers_by_tag[tag][0]  # 各タグの最初の論文を返す
    return None

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
    
    # 優先順位に基づいて最適な論文を選択
    best_paper = select_best_paper(papers_by_tag, TAG_PRIORITY)
    
    if not best_paper:
        print("No suitable paper found after priority filtering.")
        return
    
    # 選択した論文が既に通知済みかチェック
    if best_paper["url"] in latest_paper_urls:
        print(f"論文 {best_paper['id']} は既に通知済みです。スキップします。")
        return
    
    # 今日の新規親投稿を作成し、スレッドを開始
    try:
        parent_response = client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"📢 *最新のarXiv論文 - {datetime.now().strftime('%Y-%m-%d')}*"
        )
        thread_ts = parent_response['ts']
        
        # 選択した論文を通知
        send_message_to_slack(
            channel_id=SLACK_CHANNEL_ID,
            paper=best_paper,
            thread_ts=thread_ts
        )
            
    except SlackApiError as e:
        print(f"Error sending parent message: {e.response['error']}")

if __name__ == "__main__":
    notify_papers_to_slack()
