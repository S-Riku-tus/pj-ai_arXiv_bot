"""
arXiv論文取得サービス
arXivから論文を取得し、選択ロジックを提供する
"""
import arxiv
from typing import Dict, List, Optional, Any
from ..config.settings import Config


class ArxivService:
    """arXiv論文取得サービス"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tags = config.tags
        self.tag_priority = config.tag_priority
    
    def fetch_arxiv_papers(self) -> Dict[str, List[Dict[str, Any]]]:
        """各タグにつき1つずつ最新の論文を取得する"""
        all_papers = {}

        for tag in self.tags:
            try:
                # 日付フィルタなしで、最新の論文を取得（各タグ1件のみ）
                query = f"cat:{tag}"
                
                # 最新バージョンのarxivライブラリに対応
                search = arxiv.Search(
                    query=query,
                    max_results=1,  # 各カテゴリで最大1件取得
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )
                
                papers = list(search.results())
                formatted_papers = []
                
                for paper in papers:
                    # 論文情報を整形（最新バージョンに対応）
                    paper_info = {
                        "id": paper.entry_id.split('/')[-1],  # get_short_id()の代替
                        "title": paper.title,
                        "url": paper.entry_id,
                        "authors": ", ".join([author.name for author in paper.authors]),
                        "published": paper.published.strftime("%Y-%m-%d") if paper.published else "Unknown",
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
    
    def select_best_paper(self, papers_by_tag: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
        """
        優先順位の高いカテゴリから順に論文を探し、最も優先度の高い論文を返す
        
        Args:
            papers_by_tag (dict): タグごとの論文リスト
        
        Returns:
            dict or None: 最適な論文、なければNone
        """
        for tag in self.tag_priority:
            if tag in papers_by_tag and papers_by_tag[tag]:
                return papers_by_tag[tag][0]  # 各タグの最初の論文を返す
        return None
    
    def has_papers(self, papers_by_tag: Dict[str, List[Dict[str, Any]]]) -> bool:
        """論文が存在するかチェック"""
        return any(len(papers) > 0 for papers in papers_by_tag.values())
