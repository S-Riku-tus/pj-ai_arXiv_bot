import os
import json
import re
import arxiv
import openai
import google.generativeai as genai
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv, find_dotenv
from datetime import datetime

# .env の読み込み（強制的に再読み込み）
load_dotenv(find_dotenv(), override=True)

# 設定ファイルのパス（従来の設定ファイルのみ使用）
CONFIG_FILE = "config.json"

# LaTeX数式をスラック表示用にフォーマットする関数
def format_latex_for_slack(text):
    """
    LaTeX形式の数式記号をスラック表示用に変換する
    
    Args:
        text (str): LaTeX形式の数式を含むテキスト
        
    Returns:
        str: スラック表示用に変換されたテキスト
    """
    if not text:
        return ""
        
    # 上付き文字の処理（H^3 → H³）
    text = re.sub(r'(\w)\^3', r'\1³', text)
    text = re.sub(r'(\w)\^2', r'\1²', text)
    text = re.sub(r'(\w)\^1', r'\1¹', text)
    
    # 数式の処理
    # \mathbf{H}^3 → H³ (太字表記を通常表記に)
    text = re.sub(
        r'\\mathbf\{(\w+)\}\^(\d+)', 
        lambda m: m.group(1) + _get_superscript(m.group(2)), 
        text
    )
    
    # ${H}^3$ → H³ (数式環境内の上付き表記)
    text = re.sub(
        r'\$\{(\w+)\}\^(\d+)\$', 
        lambda m: m.group(1) + _get_superscript(m.group(2)), 
        text
    )
    
    # $H^3$ → H³ (単純な数式環境内の上付き表記)
    text = re.sub(
        r'\$(\w+)\^(\d+)\$', 
        lambda m: m.group(1) + _get_superscript(m.group(2)), 
        text
    )
    
    # Triply-Hierarchical など複合語のハイフン処理を保持
    text = re.sub(r'([A-Za-z]+)-([A-Za-z]+)', r'\1-\2', text)
    
    # 数式環境のドル記号を削除
    text = re.sub(r'\$(.*?)\$', r'\1', text)
    
    return text

# 数字を上付き文字に変換するヘルパー関数
def _get_superscript(num_str):
    """数字を上付き文字に変換する"""
    superscript_map = {
        '0': '⁰',
        '1': '¹',
        '2': '²',
        '3': '³',
        '4': '⁴',
        '5': '⁵',
        '6': '⁶',
        '7': '⁷',
        '8': '⁸',
        '9': '⁹'
    }
    result = ''
    for digit in num_str:
        if digit in superscript_map:
            result += superscript_map[digit]
        else:
            result += digit
    return result

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
AI_SERVICE = os.getenv("AI_SERVICE", "gemini")
# 値に空白やコメントが含まれている場合を考慮してトリム
if AI_SERVICE:
    # 空白やコメントを削除
    AI_SERVICE = AI_SERVICE.split('#')[0].strip().lower()
SLACK_CHANNELS = os.getenv("SLACK_CHANNELS", "")
SLACK_CHANNEL_ID = None
ENABLE_NOTION = os.getenv("ENABLE_NOTION", "false").lower() == "true"

# 環境変数の値を診断のために出力
print(f"AI_SERVICE: '{AI_SERVICE}'")
if GEMINI_API_KEY:
    print(f"GEMINI_API_KEY: '{GEMINI_API_KEY[:5]}...(省略)...'")
else:
    print("GEMINI_API_KEY: Not set")

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
    print("AI_SERVICE", AI_SERVICE)
    print("GEMINI_API_KEY", GEMINI_API_KEY)
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
        prompt = f"""以下の学術論文の情報を日本語に翻訳し、要約してください。

論文タイトル: {paper['title']}
著者: {paper['authors']}
出版日: {paper['published']}

アブストラクト:
{paper['summary']}

以下の3つの部分に分けて出力してください:
1. 日本語タイトル:
（ここに日本語タイトルを記入）

2. 日本語要約:
（ここに400-600文字の日本語要約を記入）

3. 重要なQ&A:
Q1: （重要な質問1）
A1: （その回答）
Q2: （重要な質問2）
A2: （その回答）
（3-5個のQ&Aペアを作成してください）
"""

        # UTF-8でエンコードしたテキストのみを使用
        safe_prompt = prompt.encode('utf-8', errors='ignore').decode('utf-8')
        
        # システムプロンプトも同様に処理
        system_prompt = "あなたは英語の学術論文を日本語に翻訳・要約する専門家です。数式や専門用語も正確に翻訳してください。"
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
        
        # 結果を解析（パターンマッチングで各セクションを抽出）
        title_match = re.search(
            r'1\.\s*日本語タイトル:\s*(.+?)(?=\n\n|\n2\.)', 
            result, 
            re.DOTALL
        )
        summary_match = re.search(
            r'2\.\s*日本語要約:\s*(.+?)(?=\n\n|\n3\.)', 
            result, 
            re.DOTALL
        )
        qa_match = re.search(r'3\.\s*重要なQ&A:\s*(.+)', result, re.DOTALL)
        
        translated_title = title_match.group(1).strip() if title_match else paper["title"]
        translated_summary = summary_match.group(1).strip() if summary_match else "要約の生成に失敗しました。"
        key_qa = qa_match.group(1).strip() if qa_match else "重要なQ&Aの生成に失敗しました。"
        
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
        prompt = f"""以下の学術論文の情報を日本語に翻訳し、要約してください。

論文タイトル: {paper['title']}
著者: {paper['authors']}
出版日: {paper['published']}

アブストラクト:
{paper['summary']}

以下の3つの部分に分けて出力してください:
1. 日本語タイトル:
（ここに日本語タイトルを記入）

2. 日本語要約:
（ここに400-600文字の日本語要約を記入）

3. 重要なQ&A:
Q1: （重要な質問1）
A1: （その回答）
Q2: （重要な質問2）
A2: （その回答）
（3-5個のQ&Aペアを作成してください）
"""
        
        # Gemini APIを呼び出し
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = model.generate_content(prompt)
        
        # レスポンスから結果を取得
        result = response.text
        
        # 結果を解析（パターンマッチングで各セクションを抽出）
        title_match = re.search(
            r'1\.\s*日本語タイトル:\s*(.+?)(?=\n\n|\n2\.)', 
            result, 
            re.DOTALL
        )
        summary_match = re.search(
            r'2\.\s*日本語要約:\s*(.+?)(?=\n\n|\n3\.)', 
            result, 
            re.DOTALL
        )
        qa_match = re.search(r'3\.\s*重要なQ&A:\s*(.+)', result, re.DOTALL)
        
        translated_title = title_match.group(1).strip() if title_match else paper["title"]
        translated_summary = summary_match.group(1).strip() if summary_match else "要約の生成に失敗しました。"
        key_qa = qa_match.group(1).strip() if qa_match else "重要なQ&Aの生成に失敗しました。"
        
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
        
        # 数式表記のクリーニング（LaTeX形式の数式を適切に表示）
        title = format_latex_for_slack(paper['title'])
        translated_title = format_latex_for_slack(translation['translated_title'])
        translated_summary = format_latex_for_slack(translation['translated_summary'])
        key_qa = format_latex_for_slack(translation['key_qa'])
        
        # Slack用に改行とフォーマットを改善したブロック
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*【タイトル】*\n{translated_title}\n\n*【原題】*\n{title}\n\n*【公開日】*\n{paper['published']}\n\n*【URL】*\n{paper['url']}\n\n*【重要なポイント】*\n{key_qa}\n\n*【要約】*\n{translated_summary}"
                }
            }
        ]
    except Exception as e:
        print(f"Error preparing message: {e}")
        # エラーが発生した場合は元の論文情報のみを表示
        text_fallback = f"{paper['title']} - {paper['url']}"
        
        title = format_latex_for_slack(paper['title'])
        summary = format_latex_for_slack(paper['summary'])
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*【タイトル】*\n{title}\n\n*【公開日】*\n{paper['published']}\n\n*【URL】*\n{paper['url']}\n\n*【要約】*\n{summary}"
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
