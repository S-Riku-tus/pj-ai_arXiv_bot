"""
Slack通知サービス
Slackへのメッセージ送信、履歴管理、重複チェック機能
"""
import re
from datetime import datetime
from typing import Dict, Any, Optional, Set
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..config.settings import Config
from ..utils.formatters import format_latex_for_slack
from .ai_service import AIService


class SlackService:
    """Slack通知サービス"""
    
    def __init__(self, config: Config, ai_service: AIService):
        self.config = config
        self.ai_service = ai_service
        self.slack_channel_id = config.slack_channel_id
        self.client = WebClient(token=config.slack_token)
    
    def notify_paper(self, paper: Dict[str, Any]) -> bool:
        """論文をSlackに通知する"""
        if not self.slack_channel_id:
            print("❌ Error: Slack channel ID is not set.")
            return False
        
        # 最新の親投稿から投稿された論文のURLを取得
        latest_paper_urls = self._get_latest_parent_paper_urls()
        
        # 選択した論文が既に通知済みかチェック
        if paper["url"] in latest_paper_urls:
            print(f"論文 {paper['id']} は既に通知済みです。スキップします。")
            return False
        
        try:
            # 今日の新規親投稿を作成し、スレッドを開始
            parent_response = self.client.chat_postMessage(
                channel=self.slack_channel_id,
                text=f"📢 *最新のarXiv論文 - {datetime.now().strftime('%Y-%m-%d')}*"
            )
            thread_ts = parent_response['ts']
            
            # 選択した論文を通知
            self._send_message_to_slack(
                channel_id=self.slack_channel_id,
                paper=paper,
                thread_ts=thread_ts
            )
            
            return True
            
        except SlackApiError as e:
            print(f"Error sending parent message: {e.response['error']}")
            return False
    
    def _send_message_to_slack(self, channel_id: str, paper: Dict[str, Any], thread_ts: Optional[str] = None) -> Optional[str]:
        """Slack にメッセージを送信する"""
        # 論文の翻訳・要約を取得
        try:
            translation = self.ai_service.translate_and_summarize_paper(paper)
            
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
            response = self.client.chat_postMessage(
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
    
    def _get_latest_parent_paper_urls(self) -> Set[str]:
        """Slack チャンネル内で最新の親投稿のスレッドから、投稿された論文のURLを抽出する"""
        try:
            # チャンネルの直近20件のメッセージを取得
            result = self.client.conversations_history(channel=self.slack_channel_id, limit=20)
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
            replies_result = self.client.conversations_replies(
                channel=self.slack_channel_id,
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
