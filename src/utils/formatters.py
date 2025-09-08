"""
フォーマッターユーティリティ
LaTeX数式のSlack表示用フォーマットなど
"""
import re


def format_latex_for_slack(text: str) -> str:
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


def _get_superscript(num_str: str) -> str:
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
