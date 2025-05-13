import arxiv
from datetime import datetime, timedelta

def test_arxiv_search():
    """arXiv APIから論文が取得できるかテストする"""
    
    # テスト用のカテゴリ一覧
    test_categories = ["cs.AI", "cs.LG", "cs.CL", "cs.CV"]
    
    # 日付範囲を広く取る（過去30日）
    days_ago = datetime.now() - timedelta(days=30)
    date_filter = f"submittedDate:[{days_ago.strftime('%Y%m%d')}* TO *]"
    
    print("arXiv APIのテストを開始します...")
    
    for category in test_categories:
        # カテゴリで絞り込み
        query = f"cat:{category}"
        
        try:
            # まず日付フィルタなしで検索
            print(f"\n======= カテゴリ: {category} （日付フィルタなし） =======")
            search = arxiv.Search(
                query=query,
                max_results=3,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            papers = list(search.results())
            print(f"論文数: {len(papers)}")
            
            for i, paper in enumerate(papers):
                print(f"[{i+1}] {paper.title} ({paper.published.strftime('%Y-%m-%d')})")
            
            # 次に日付フィルタありで検索
            print(f"\n======= カテゴリ: {category} （日付フィルタあり） =======")
            query_with_date = f"cat:{category} AND {date_filter}"
            search_with_date = arxiv.Search(
                query=query_with_date,
                max_results=3,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            papers_with_date = list(search_with_date.results())
            print(f"論文数: {len(papers_with_date)}")
            
            for i, paper in enumerate(papers_with_date):
                print(f"[{i+1}] {paper.title} ({paper.published.strftime('%Y-%m-%d')})")
                
        except Exception as e:
            print(f"エラー: {e}")
    
    print("\nテスト完了")

if __name__ == "__main__":
    test_arxiv_search() 