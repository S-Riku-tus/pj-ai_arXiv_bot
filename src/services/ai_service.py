"""
AI翻訳・要約サービス
Gemini APIを使用した論文の翻訳・要約機能
"""
import re
import google.generativeai as genai
from typing import Dict, Any
from ..config.settings import Config


class AIService:
    """AI翻訳・要約サービス（Gemini専用）"""
    
    def __init__(self, config: Config):
        self.config = config
        self.gemini_api_key = config.gemini_api_key
        
        # API設定
        self._setup_gemini()
    
    def _setup_gemini(self):
        """Gemini APIの設定"""
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            print("Using Gemini API for translation and summarization")
        else:
            print("Warning: Gemini API key is not set. Translation features will be disabled.")
    
    def translate_and_summarize_paper(self, paper: Dict[str, Any]) -> Dict[str, str]:
        """Gemini APIを使って論文を翻訳・要約する"""
        if not self.gemini_api_key:
            return {
                "translated_title": paper["title"],
                "translated_summary": "Gemini API key is not set. Translation unavailable.",
                "key_qa": "Gemini API key is not set. Key Q&A unavailable."
            }
        
        return self._translate_and_summarize_paper_gemini(paper)
    
    def _translate_and_summarize_paper_gemini(self, paper: Dict[str, Any]) -> Dict[str, str]:
        """Gemini APIを使って論文を翻訳・要約する"""
        if not self.gemini_api_key:
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
            
            return self._parse_ai_response(result, paper)
            
        except Exception as e:
            print(f"Error translating and summarizing paper with Gemini: {e}")
            return {
                "translated_title": paper["title"],
                "translated_summary": f"翻訳・要約中にエラーが発生しました: {str(e)}",
                "key_qa": "重要なQ&Aは利用できません。"
            }
    
    def _parse_ai_response(self, result: str, paper: Dict[str, Any]) -> Dict[str, str]:
        """AI レスポンスを解析して各セクションを抽出"""
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
