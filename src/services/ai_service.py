"""
AI翻訳・要約サービス
OpenAIとGemini APIを使用した論文の翻訳・要約機能
"""
import re
import openai
import google.generativeai as genai
from typing import Dict, Any
from ..config.settings import Config


class AIService:
    """AI翻訳・要約サービス"""
    
    def __init__(self, config: Config):
        self.config = config
        self.ai_service = config.ai_service
        self.openai_api_key = config.openai_api_key
        self.gemini_api_key = config.gemini_api_key
        
        # API設定
        self._setup_apis()
    
    def _setup_apis(self):
        """AI APIの設定"""
        if self.ai_service == "openai" and self.openai_api_key:
            openai.api_key = self.openai_api_key
            print("Using OpenAI API for translation and summarization")
        elif self.ai_service == "gemini" and self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            print("Using Gemini API for translation and summarization")
        else:
            print("Warning: No valid AI API key set. Translation features will be disabled.")
    
    def translate_and_summarize_paper(self, paper: Dict[str, Any]) -> Dict[str, str]:
        """適切なAIサービスを使って論文を翻訳・要約する"""
        if self.ai_service == "gemini" and self.gemini_api_key:
            return self._translate_and_summarize_paper_gemini(paper)
        elif self.ai_service == "openai" and self.openai_api_key:
            return self._translate_and_summarize_paper_openai(paper)
        else:
            # 翻訳機能が利用できない場合は元の情報を返す
            return {
                "translated_title": paper["title"],
                "translated_summary": paper["summary"][:500] + "...",
                "key_qa": "AI translation service is not available."
            }
    
    def _translate_and_summarize_paper_openai(self, paper: Dict[str, Any]) -> Dict[str, str]:
        """OpenAI APIを使って論文を翻訳・要約する"""
        if not self.openai_api_key:
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
            
            return self._parse_ai_response(result, paper)
            
        except Exception as e:
            print(f"Error translating and summarizing paper with OpenAI: {e}")
            return {
                "translated_title": paper["title"],
                "translated_summary": f"翻訳・要約中にエラーが発生しました: {str(e)}",
                "key_qa": "重要なQ&Aは利用できません。"
            }
    
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
