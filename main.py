"""
arXiv論文通知Bot - メイン実行ファイル
ワークフローのみを記述し、詳細な処理は各サービスに委譲
"""
from src.config import Config
from src.services import ArxivService, AIService, SlackService


def main():
    """メイン実行関数"""
    try:
        # 設定の読み込み
        config = Config()
        
        # サービスの初期化
        arxiv_service = ArxivService(config)
        ai_service = AIService(config)
        slack_service = SlackService(config, ai_service)
        
        # メインワークフロー
        print("🔍 arXiv論文を取得中...")
        papers_by_tag = arxiv_service.fetch_arxiv_papers()
        
        # 今日の記事が見つかったかどうか
        if not arxiv_service.has_papers(papers_by_tag):
            print("No papers found for any tag.")
            return
        
        # 優先順位に基づいて最適な論文を選択
        print("📋 最適な論文を選択中...")
        best_paper = arxiv_service.select_best_paper(papers_by_tag)
        
        if not best_paper:
            print("No suitable paper found after priority filtering.")
            return
        
        # 選択した論文をSlackに通知
        print(f"📤 論文を通知中: {best_paper['title'][:50]}...")
        success = slack_service.notify_paper(best_paper)
        
        if success:
            print("✅ 論文の通知が完了しました。")
        else:
            print("❌ 論文の通知に失敗しました。")
            
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    main()
