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
    
    # 1. 分数とルートの処理（最初に処理）
    text = _convert_fractions_and_roots(text)
    
    # 2. LaTeXコマンドの処理
    text = _convert_latex_commands(text)
    
    # 3. 下付き文字の処理（H_{2} → H₂）
    text = _convert_subscripts(text)
    
    # 4. 上付き文字の処理（H^3 → H³）
    text = _convert_superscripts(text)
    
    # 5. 数式環境の処理
    text = _convert_math_environments(text)
    
    # 6. その他のLaTeX記号の処理
    text = _convert_other_latex_symbols(text)
    
    return text


def _convert_fractions_and_roots(text: str) -> str:
    """分数とルートを変換する"""
    # \frac{a}{b} → a/b
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)
    
    # \sqrt{x} → √x
    text = re.sub(r'\\sqrt\{([^}]+)\}', r'√\1', text)
    
    # \sqrt[n]{x} → ⁿ√x
    text = re.sub(r'\\sqrt\[([^\]]+)\]\{([^}]+)\}', r'\1√\2', text)
    
    return text


def _convert_subscripts(text: str) -> str:
    """下付き文字を変換する"""
    # H_{2} → H₂ のパターン（アンダースコアの後に中括弧がある場合）
    text = re.sub(
        r'(\w+)_\{([^}]+)\}', 
        lambda m: m.group(1) + _convert_subscript_content(m.group(2)), 
        text
    )
    
    # 数式環境内の下付き文字も処理
    text = re.sub(
        r'\$(\w+)_\{([^}]+)\}\$', 
        lambda m: m.group(1) + _convert_subscript_content(m.group(2)), 
        text
    )
    
    return text


def _convert_subscript_content(content: str) -> str:
    """下付き文字の内容を変換する"""
    result = ""
    i = 0
    while i < len(content):
        char = content[i]
        if char.isdigit():
            # 数字の場合は下付き文字に変換
            result += _get_subscript(char)
        elif char.isalpha():
            # 文字の場合は下付き文字に変換
            result += _get_subscript_letter(char)
        elif char == '=':
            # 等号の場合は下付き等号に変換
            result += '₌'
        else:
            # その他の文字（カンマ、ハイフンなど）はそのまま
            result += char
        i += 1
    return result


def _get_subscript_letter(letter: str) -> str:
    """文字を下付き文字に変換する"""
    subscript_letters = {
        'a': 'ₐ', 'b': 'ᵦ', 'c': 'ᵧ', 'd': 'ᵨ', 'e': 'ₑ', 'f': 'ᵩ', 'g': 'ᵪ',
        'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ',
        'o': 'ₒ', 'p': 'ₚ', 'q': 'ᵠ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
        'v': 'ᵥ', 'w': 'ᵦ', 'x': 'ₓ', 'y': 'ᵧ', 'z': 'ᵨ',
        'A': 'ₐ', 'B': 'ᵦ', 'C': 'ᵧ', 'D': 'ᵨ', 'E': 'ₑ', 'F': 'ᵩ', 'G': 'ᵪ',
        'H': 'ₕ', 'I': 'ᵢ', 'J': 'ⱼ', 'K': 'ₖ', 'L': 'ₗ', 'M': 'ₘ', 'N': 'ₙ',
        'O': 'ₒ', 'P': 'ₚ', 'Q': 'ᵠ', 'R': 'ᵣ', 'S': 'ₛ', 'T': 'ₜ', 'U': 'ᵤ',
        'V': 'ᵥ', 'W': 'ᵦ', 'X': 'ₓ', 'Y': 'ᵧ', 'Z': 'ᵨ'
    }
    return subscript_letters.get(letter, letter)


def _convert_superscripts(text: str) -> str:
    """上付き文字を変換する"""
    # H^3 → H³ のパターン（数字のみ）
    text = re.sub(
        r'(\w+)\^(\d+)', 
        lambda m: m.group(1) + _convert_superscript_content(m.group(2)), 
        text
    )
    
    # 数式環境内の上付き文字も処理
    text = re.sub(
        r'\$(\w+)\^(\d+)\$', 
        lambda m: m.group(1) + _convert_superscript_content(m.group(2)), 
        text
    )
    
    # 複雑な上付き文字（中括弧で囲まれた場合）
    text = re.sub(
        r'(\w+)\^\{([^}]+)\}', 
        lambda m: m.group(1) + _convert_superscript_content_smart(m.group(2)), 
        text
    )
    
    return text


def _convert_superscript_content_smart(content: str) -> str:
    """上付き文字の内容をスマートに変換する"""
    # LaTeXコマンドが含まれている場合は、まずLaTeXコマンドを処理
    if '\\' in content:
        # \times を × に変換
        content = content.replace('\\times', '×')
        # その他のLaTeXコマンドも処理
        content = _convert_other_latex_symbols(content)
    
    # スペースを削除
    content = content.replace(' ', '')
    
    # 変換された内容を上付き文字に変換
    return _convert_superscript_content(content)


def _convert_superscript_content(content: str) -> str:
    """上付き文字の内容を変換する"""
    result = ""
    i = 0
    while i < len(content):
        char = content[i]
        if char.isdigit():
            # 数字の場合は上付き文字に変換
            result += _get_superscript(char)
        elif char.isalpha():
            # 文字の場合は上付き文字に変換
            result += _get_superscript_letter(char)
        elif char == '+':
            # プラス記号の場合は上付きプラスに変換
            result += '⁺'
        elif char == '-':
            # マイナス記号の場合は上付きマイナスに変換
            result += '⁻'
        elif char == '(':
            # 開き括弧の場合は上付き括弧に変換
            result += '⁽'
        elif char == ')':
            # 閉じ括弧の場合は上付き括弧に変換
            result += '⁾'
        elif char == '×':
            # 乗算記号の場合は上付き乗算記号に変換
            result += 'ˣ'
        else:
            # その他の文字（カンマ、ハイフンなど）はそのまま
            result += char
        i += 1
    return result


def _get_superscript_letter(letter: str) -> str:
    """文字を上付き文字に変換する"""
    superscript_letters = {
        'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ', 'g': 'ᵍ',
        'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ', 'n': 'ⁿ',
        'o': 'ᵒ', 'p': 'ᵖ', 'q': 'ᵠ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
        'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ',
        'A': 'ᴬ', 'B': 'ᴮ', 'C': 'ᶜ', 'D': 'ᴰ', 'E': 'ᴱ', 'F': 'ᶠ', 'G': 'ᴳ',
        'H': 'ᴴ', 'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ', 'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ',
        'O': 'ᴼ', 'P': 'ᴾ', 'Q': 'ᵠ', 'R': 'ᴿ', 'S': 'ˢ', 'T': 'ᵀ', 'U': 'ᵁ',
        'V': 'ⱽ', 'W': 'ᵂ', 'X': 'ˣ', 'Y': 'ʸ', 'Z': 'ᶻ'
    }
    return superscript_letters.get(letter, letter)


def _convert_latex_commands(text: str) -> str:
    """LaTeXコマンドを変換する"""
    # \mathbf{text} → text (太字を通常に)
    text = re.sub(r'\\mathbf\{([^}]+)\}', r'\1', text)
    
    # \text{text} → text
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    
    # \mathit{text} → text (イタリックを通常に)
    text = re.sub(r'\\mathit\{([^}]+)\}', r'\1', text)
    
    # \mathrm{text} → text (ローマン体を通常に)
    text = re.sub(r'\\mathrm\{([^}]+)\}', r'\1', text)
    
    # \mathcal{text} → text (カリグラフィーを通常に)
    text = re.sub(r'\\mathcal\{([^}]+)\}', r'\1', text)
    
    # \mathbb{text} → text (黒板太字を通常に、ただし特別な文字は変換)
    text = re.sub(r'\\mathbb\{R\}', 'ℝ', text)
    text = re.sub(r'\\mathbb\{N\}', 'ℕ', text)
    text = re.sub(r'\\mathbb\{Z\}', 'ℤ', text)
    text = re.sub(r'\\mathbb\{Q\}', 'ℚ', text)
    text = re.sub(r'\\mathbb\{C\}', 'ℂ', text)
    text = re.sub(r'\\mathbb\{([^}]+)\}', r'\1', text)
    
    return text


def _convert_math_environments(text: str) -> str:
    """数式環境を変換する"""
    # ドル記号で囲まれた数式環境を処理
    text = re.sub(r'\$(.*?)\$', lambda m: _process_math_content(m.group(1)), text)
    
    return text


def _process_math_content(math_text: str) -> str:
    """数式環境内の内容を処理する"""
    # 既に処理された下付き・上付き文字はそのまま
    # その他のLaTeXコマンドを処理
    math_text = _convert_latex_commands(math_text)
    return math_text


def _convert_other_latex_symbols(text: str) -> str:
    """その他のLaTeX記号を変換する"""
    # ギリシャ文字の変換
    greek_letters = {
        r'\\alpha': 'α', r'\\beta': 'β', r'\\gamma': 'γ', r'\\delta': 'δ',
        r'\\epsilon': 'ε', r'\\zeta': 'ζ', r'\\eta': 'η', r'\\theta': 'θ',
        r'\\iota': 'ι', r'\\kappa': 'κ', r'\\lambda': 'λ', r'\\mu': 'μ',
        r'\\nu': 'ν', r'\\xi': 'ξ', r'\\omicron': 'ο', r'\\pi': 'π',
        r'\\rho': 'ρ', r'\\sigma': 'σ', r'\\tau': 'τ', r'\\upsilon': 'υ',
        r'\\phi': 'φ', r'\\chi': 'χ', r'\\psi': 'ψ', r'\\omega': 'ω',
        r'\\Gamma': 'Γ', r'\\Delta': 'Δ', r'\\Theta': 'Θ', r'\\Lambda': 'Λ',
        r'\\Xi': 'Ξ', r'\\Pi': 'Π', r'\\Sigma': 'Σ', r'\\Upsilon': 'Υ',
        r'\\Phi': 'Φ', r'\\Psi': 'Ψ', r'\\Omega': 'Ω'
    }
    
    for latex_cmd, unicode_char in greek_letters.items():
        text = re.sub(latex_cmd, unicode_char, text)
    
    # 数学記号の変換
    math_symbols = {
        r'\\times': '×', r'\\div': '÷', r'\\pm': '±', r'\\mp': '∓',
        r'\\leq': '≤', r'\\geq': '≥', r'\\neq': '≠', r'\\approx': '≈',
        r'\\equiv': '≡', r'\\propto': '∝', r'\\infty': '∞', r'\\sum': '∑',
        r'\\prod': '∏', r'\\int': '∫', r'\\partial': '∂', r'\\nabla': '∇',
        r'\\in': '∈', r'\\notin': '∉', r'\\subset': '⊂', r'\\supset': '⊃',
        r'\\cup': '∪', r'\\cap': '∩', r'\\emptyset': '∅', r'\\rightarrow': '→',
        r'\\leftarrow': '←', r'\\leftrightarrow': '↔', r'\\Rightarrow': '⇒',
        r'\\Leftarrow': '⇐', r'\\Leftrightarrow': '⇔',
        r'\\cdot': '·', r'\\bullet': '•', r'\\circ': '∘', r'\\star': '⋆',
        r'\\ast': '∗', r'\\oplus': '⊕', r'\\ominus': '⊖', r'\\otimes': '⊗',
        r'\\odot': '⊙', r'\\wedge': '∧', r'\\vee': '∨', r'\\neg': '¬',
        r'\\land': '∧', r'\\lor': '∨', r'\\forall': '∀', r'\\exists': '∃'
    }
    
    for latex_cmd, unicode_char in math_symbols.items():
        text = re.sub(latex_cmd, unicode_char, text)
    
    return text


def _get_subscript(num_str: str) -> str:
    """数字を下付き文字に変換する"""
    subscript_map = {
        '0': '₀',
        '1': '₁',
        '2': '₂',
        '3': '₃',
        '4': '₄',
        '5': '₅',
        '6': '₆',
        '7': '₇',
        '8': '₈',
        '9': '₉'
    }
    result = ''
    for digit in num_str:
        if digit in subscript_map:
            result += subscript_map[digit]
        else:
            result += digit
    return result


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
