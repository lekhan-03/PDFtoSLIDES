"""formula_render.py — Universal scientific text renderer for PPTX slides.

Renders ENTIRE text blocks as single PNG images using Matplotlib's built-in
math-text engine. This guarantees pixel-perfect layout for any combination
of plain text and scientific formulas.

Public API
----------
auto_latex(text) -> str
    Convert science notation in plain text to $LaTeX$ dollar-sign markers.
    Works for ALL subjects: Chemistry, Physics, Math, Biology.

render_text_block(text, width_in, font_size, fg_hex, bg_hex, dpi, bold)
    -> Path to cached PNG, or None on failure.

text_needs_latex(text) -> bool
    Returns True if the text contains formulas that need special rendering.

Subject coverage
----------------
Chemistry:  H2SO4, CaCO3, Na2SO4, Cu2+, Fe3+, 3d10, t2g3, eg1, Δo
Physics:    α β γ λ μ ω Σ π θ ρ ε (auto-converted Unicode Greek letters)
Math:       explicit $...$ blocks rendered directly by matplotlib
Biology:    plain English, no changes needed
"""
from __future__ import annotations

import hashlib
import re
import textwrap
import tempfile
import warnings
from pathlib import Path

# ── Cache directory for rendered PNGs ─────────────────────────────────────────
_CACHE_DIR = Path(tempfile.gettempdir()) / "mcq2slides_blocks"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Cache directory for pandoc (if needed) ────────────────────────────────────
_CACHE_DIR = Path(tempfile.gettempdir()) / "mcq2slides_pandoc"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

try:
    import pypandoc
    _HAS_PANDOC = True
except ImportError:
    _HAS_PANDOC = False


# ─────────────────────────────────────────────────────────────────────────────
# Auto-detection rules: plain text  →  $LaTeX$ markers
# Rules are applied IN ORDER. More specific rules MUST come first.
# ─────────────────────────────────────────────────────────────────────────────

_GREEK_MAP = {
    "α":"alpha","β":"beta","γ":"gamma","δ":"delta","ε":"varepsilon","ζ":"zeta",
    "η":"eta","θ":"theta","ι":"iota","κ":"kappa","λ":"lambda","μ":"mu","ν":"nu",
    "ξ":"xi","ο":"o","π":"pi","ρ":"rho","σ":"sigma","τ":"tau","υ":"upsilon",
    "φ":"phi","χ":"chi","ψ":"psi","ω":"omega","Α":"Alpha","Β":"Beta","Γ":"Gamma",
    "Δ":"Delta","Ε":"Epsilon","Ζ":"Zeta","Η":"Eta","Θ":"Theta","Ι":"Iota",
    "Κ":"Kappa","Λ":"Lambda","Μ":"Mu","Ν":"Nu","Ξ":"Xi","Ο":"O","Π":"Pi",
    "Ρ":"Rho","Σ":"Sigma","Τ":"Tau","Υ":"Upsilon","Φ":"Phi","Χ":"Chi","Ψ":"Psi","Ω":"Omega"
}

_SUPERSCRIPT_MAP = str.maketrans(
    '\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079'
    '\u207A\u207B\u02E3\u207F\u1D4E\u02B2\u2071',
    '0123456789+-xni j'
)

_SUBSCRIPT_MAP = str.maketrans(
    '\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u208A\u208B\u2093',
    '0123456789+-x',
)


def _clean_inner(s: str) -> str:
    return s.strip().replace('\uE000', '').replace('\uE001', '').replace('$', '')


def _chem_formula_sub(m: re.Match) -> str:
    """Convert chemical formula to LaTeX, handling trailing ion charges."""
    raw = m.group(0)
    if not re.search(r'[A-Za-z]', raw):
        return raw
    if raw.count('(') != raw.count(')'):
        return raw

    charge_match = re.search(r'(\d?)([+-])$', raw)
    if charge_match:
        formula_part = raw[:charge_match.start()]
        charge = charge_match.group(1) + charge_match.group(2)
        body = re.sub(r'([A-Za-z\]\)])(\d+)', r'\1_{\2}', formula_part)
        return f'\uE000{body}^{{{charge}}}\uE001'
    body = re.sub(r'([A-Za-z\]\)])(\d+)', r'\1_{\2}', raw)
    return f'\uE000{body}\uE001'


def _ion_charge_sub(m: re.Match) -> str:
    """Cu2+  →  $Cu^{2+}$"""
    return f'\uE000{m.group(1)}^{{{m.group(2)}}}\uE001'


def _econf_sub(m: re.Match) -> str:
    """3d10  →  $3d^{10}$"""
    return f'\uE000{m.group(1)}{m.group(2)}^{{{m.group(3)}}}\uE001'


def _d_orbital_sub(m: re.Match) -> str:
    """d4 ion  →  $d^{4}$ ion"""
    return f'\uE000{m.group(1)}^{{{m.group(2)}}}\uE001 '


def _sci_full_sub(m: re.Match) -> str:
    """2.5 x 10-3  →  $2.5 \\times 10^{-3}$"""
    return f'\uE000{m.group(1)} \\times 10^{{{m.group(2)}}}\uE001'


def _sci_alone_sub(m: re.Match) -> str:
    """10-5  →  $10^{-5}$"""
    exp = m.group(2) or m.group(5) or m.group(8) or m.group(11)
    return f'\uE00010^{{{exp}}}\uE001'


def _units_sub(m: re.Match) -> str:
    """mol-1  →  $mol^{-1}$"""
    word = m.group(1)
    if word.lower() in ('step', 'case', 'type', 'part', 'page'):
        return m.group(0)
    return f'\uE000{word}^{{-{m.group(2)}}}\uE001'


def _frac_sub(m: re.Match) -> str:
    """(num)/(den)  →  $\\frac{num}{den}$"""
    num = _clean_inner(m.group(1))
    den = _clean_inner(m.group(2))
    return f'\uE000\\frac{{{num}}}{{{den}}}\uE001'


def _sqrt_sub(m: re.Match) -> str:
    """sqrt(expr)  →  $\\sqrt{expr}$"""
    inner = _clean_inner(m.group(1))
    return f'\uE000\\sqrt{{{inner}}}\uE001'


def _root_sub(m: re.Match) -> str:
    """root(n, expr)  →  $\\sqrt[n]{expr}$"""
    n = _clean_inner(m.group(1))
    expr = _clean_inner(m.group(2))
    return f'\uE000\\sqrt[{n}]{{{expr}}}\uE001'


def _trig_sub(m: re.Match) -> str:
    """sin⁡x  →  $\\sin x$"""
    func = m.group(1).lower()
    if func in ('cosec', 'csc'):
        func = 'csc'
    arg = next((group for group in m.groups()[1:] if group), '').strip()
    if arg.startswith('{') and arg.endswith('}'):
        arg = arg[1:-1]
    elif arg.startswith('(') and arg.endswith(')'):
        arg = arg[1:-1]
    return f'\uE000\\{func}{{{arg}}}\uE001'


def _sup_unicode_sub(m: re.Match) -> str:
    """Unicode superscripts like \u02E3, \u00B2 → $^{x}$, $^{2}$"""
    base = m.group(1) or ''
    chars = m.group(2).translate(_SUPERSCRIPT_MAP).strip()
    if chars:
        return f'\uE000{base}^{{{chars}}}\uE001'
    return m.group(0)


def _lost_power_sub(m: re.Match) -> str:
    """Lost superscripts on math vars: 2x2 -> 2x^2"""
    return f'\uE000{m.group(1)}{m.group(2)}^{{{m.group(3)}}}\uE001'


def _existing_script_sub(m: re.Match) -> str:
    """Wrap bare ^{} or _{} that are already in text but outside $...$."""
    word = m.group(0)
    for t in ('cosec', 'csc', 'sin', 'cos', 'tan', 'sec', 'cot', 'log', 'ln', 'exp'):
        if word.startswith(t):
            fn = 'csc' if t in ('cosec', 'csc') else t
            rest = word[len(t):]
            return f'\uE000\\{fn}{rest}\uE001'
    return f'\uE000{word}\uE001'


def _integral_sub(m: re.Match) -> str:
    """Convert Unicode integral symbol (∫) and OMML limits into LaTeX \\int with safe space padding."""
    raw = m.group(0)
    body = raw.replace('\u222b', r'\int ').replace('\uE000', '').replace('\uE001', '').replace('$', '')
    # Translate Greek letters inside limits (e.g. \pi)
    for k, v in _GREEK_MAP.items():
        if k in body:
            body = body.replace(k, f'\\{v} ')
    body = re.sub(r'\s+', ' ', body)
    return f'\uE000{body} \uE001'


def _piecewise_sub(m: re.Match) -> str:
    r"""Convert unclosed brace piecewise notation to \begin{cases} ... \end{cases}"""
    val1 = m.group(1).strip()
    cond1 = m.group(2).strip()
    val2 = m.group(3).strip()
    cond2 = m.group(4).strip()
    
    def textify(cond):
        cond = re.sub(r'^if\s+', '', cond.strip())
        cond = re.sub(r'\bis an even function\b', r'\\text{ is an even function}', cond)
        cond = re.sub(r'\bis even function\b', r'\\text{ is an even function}', cond)
        cond = re.sub(r'\bis even\b', r'\\text{ is even}', cond)
        cond = re.sub(r'\bis an odd function\b', r'\\text{ is an odd function}', cond)
        cond = re.sub(r'\bis odd function\b', r'\\text{ is an odd function}', cond)
        cond = re.sub(r'\bis odd\b', r'\\text{ is odd}', cond)
        return '\\text{if } ' + cond
        
    cond1 = textify(cond1)
    cond2 = textify(cond2)
    val1 = val1.replace('.dx', '\\,dx').replace(' dx', '\\,dx')
    
    return f"=\uE000\\begin{{cases}} {val1} & {cond1} \\\\ {val2} & {cond2} \\end{{cases}}\uE001 "



_STRUCTURAL_RULES: list[tuple[re.Pattern, object]] = [
    # ── Strip invisible Unicode function-application char (U+2061) ─────────
    (re.compile('\u2061'), ''),

    # A single-letter base with an explicit bare subscript is unambiguous math
    # notation (x_B, K_f, p_A). Do not infer scripts in longer identifiers.
    (re.compile(r'(?<![A-Za-z0-9_])([A-Za-z])_([A-Za-z0-9])(?![A-Za-z0-9_])'),
     lambda m: f'\uE000{m.group(1)}_{{{m.group(2)}}}\uE001'),

    # Keep Unicode sub/superscripts attached to their complete base, including
    # chemistry groups such as SO₄²⁻ and mixed scripts such as x₁².
    (re.compile(r'([A-Za-zα-ωΑ-Ω0-9]+)([\u2080-\u208A\u2093]+)([\u2070\u00B9\u00B2\u00B3\u2074-\u2079\u207A\u207B\u02E3\u207F\u1D4E\u02B2\u2071]*)([A-Za-z]*)'),
     lambda m: f'\uE000{m.group(1)}_{{{m.group(2).translate(_SUBSCRIPT_MAP)}}}'
               + ('^{' + m.group(3).translate(_SUPERSCRIPT_MAP).strip() + '}' if m.group(3) else '')
               + m.group(4)
               + '\uE001'),

    # Keep square-root notation structured for simple atoms and grouped terms.
    (re.compile(r'√\(([^()]*)\)'), lambda m: f'\uE000\\sqrt{{{m.group(1)}}}\uE001'),
    (re.compile(r'√([A-Za-z0-9]+)'), lambda m: f'\uE000\\sqrt{{{m.group(1)}}}\uE001'),

    # ── Piecewise functions ──────────────────────────────────────────────────
    (re.compile(r'=\s*\{\s*(2[^,i]+?dx)\s*,?\s*if\s+(.*?)\s+(0)\s*,?\s*if\s+([^$]+?)\s*(?=\$|And|and)', re.IGNORECASE), _piecewise_sub),

    # ── Normalize duplicated OCR trig/log names: sinsin -> sin, loglog -> log ──
    (re.compile(r'\b(sin|cos|tan|sec|csc|cosec|cot|log|ln)\1\b', re.I), r'\1'),

    # ── OMML-extracted fraction notation: (num)/(den) → \frac{num}{den} ─────
    (re.compile(r'\(((?:[^()]+|\([^()]+\))++)\)/\(((?:[^()]+|\([^()]+\))++)\)'), _frac_sub),

    # ── OMML-extracted sqrt/root notation ────────────────────────────────────
    (re.compile(r'\broot\(([^,]+),\s*([^)]+)\)'), _root_sub),
    (re.compile(r'sqrt\(([^)]+)\)'), _sqrt_sub),

    # ── OMML-extracted integral symbol (with optional limits) ────────────────
    (re.compile(r'\u222b(?:(?:_|\^)\{(?:[^{}]+|\{[^}]+\})*+\})*+'), _integral_sub),

    (re.compile(r'(?<![A-Za-zα-ωΑ-Ω0-9])([A-Za-zα-ωΑ-Ω0-9)]+(?:\^|_)\{(?:[^{}]+|\{[^}]+\})*+\}(?:(?:\^|_)\{(?:[^{}]+|\{[^}]+\})*+\})*+)'),
     _existing_script_sub),

    # ── Unicode superscripts → $^{...}$ ──────────────────────────────────────
    (re.compile(r'([A-Za-zα-ωΑ-Ω0-9\)]+)?([\u2070\u00B9\u00B2\u00B3\u2074-\u2079\u207A\u207B\u02E3\u207F\u1D4E\u02B2\u2071]+)'),
     _sup_unicode_sub),
]


_SYMBOL_RULES: list[tuple[re.Pattern, object]] = [
    # ── Crystal Field Theory (must be first!) ─────────────────────────────
    (re.compile(r'\bt(\d)2g\b'),   r't2g\1'),
    (re.compile(r'\be(\d)g\b'),    r'eg\1'),
    (re.compile(r'\bt2g(\d+)'),    lambda m: f'\uE000t_{{2g}}^{{{m.group(1)}}}\uE001'),
    (re.compile(r'\bt2g\b'),       lambda m: '\uE000t_{2g}\uE001'),
    (re.compile(r'\beg(\d+)'),     lambda m: f'\uE000e_g^{{{m.group(1)}}}\uE001'),
    (re.compile(r'\beg\b'),        lambda m: '\uE000e_g\uE001'),

    # ── Trig functions run-on with argument: sinx → \sin{x} (cosec/csc before cos!) ──
    (re.compile(
        r'(?<![A-Za-z])\\?(cosec|csc|sin|cos|tan|sec|cot|log|ln|exp)'
        r'(?:\s*(\([^()]*\)|\{[^{}]*\})|\s+([A-Za-zα-ωΑ-Ω]+|\d+[A-Za-zα-ωΑ-Ω]?)\b|'
        r'([xyzθ]|\d+[xyzθ])\b)'),
     _trig_sub),

    # ── Greek letters (Unicode → LaTeX) ──────────────────────────────────────
    (re.compile('\u0394([oO0])'),       lambda m: f'\uE000\\Delta_{{{m.group(1)}}}\uE001'),
    (re.compile(r'([αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ])'),
     lambda m: f'\uE000\\{_GREEK_MAP[m.group(1)]} \uE001'),
     
    # ── Function notation: f(x), g(y) ────────────────────────────────────────
    (re.compile(r'\b([fghFGH])\(([x-zX-Z])\)'), lambda m: f'\uE000{m.group(1)}({m.group(2)})\uE001'),

    # ── Scientific Notation ──────────────────────────────────────────────────
    (re.compile(r'\uE000?\b(\d+(?:\.\d+)?)\s*(?:[xX]|\*|×|\u00D7)\s*\uE000?10\uE001?\s*(?:\^|(?=-))?\s*\{?\uE000?(-?\d+)\}?\uE001?(?!\d)'), _sci_full_sub),
    (re.compile(r'(?<!\\times\s)(?<!\\times)\uE000?\b10\uE001?(?:(\s*\^\s*\{?\uE000?)(-?\d+)(\}?)|(\s*\{?\uE000?)(-\d+)(\}?)|(\s+\{?\uE000?)(-?\d+)(\}?)|(\s*\{?\uE000?)(-?\d+)(\}?)(?=(?:[ \u00A0]*(?:[a-zA-Z]*Hz|[a-zA-Z]?Js|[a-zA-Z]?C|m/s(?:[²³]|\^[23])?|kg\b|g\b|s\b|mol\b|eV\b|V\b|A\b|K\b|J\b|N\b|W\b|Ω\b|F\b|T\b|m\b|cm\b|mm\b|μm\b|nm\b|L\b|mL\b))))\uE001?(?!\d)'), _sci_alone_sub),

    # ── Lost powers on math variables: 2x2 -> 2x^2 ───────────────────────────
    (re.compile(r'(?<![a-zA-Z])(\d*)([xyzabcnmrt])(\d+)\b'), _lost_power_sub),

    # ── Units with negative exponents: mol-1, s-1, m-3 ───────────────────────
    (re.compile(r'\b([a-zA-Z]{1,4})-(\d+)\b'), _units_sub),

    # ── Electron configurations: 3d10, 2p6, 1s2, 4f14 ──────────────────────
    (re.compile(r'\b([1-7])([spdf])(\d{1,2})\b'), _econf_sub),

    # ── Lone d/f orbital: "d4 ion" ───────────────────────────────────────────
    (re.compile(r'\b([df])(\d{1,2})\s+(?=ion\b|config|electron|orbital)'),
     _d_orbital_sub),

    # ── Coordination complexes: [Pt (NH3)2Cl2] or [Co(NH3)6]3+ ─────────────
    (re.compile(r'\[[A-Z][^\]]*\](?:\d?[+-])?'), _chem_formula_sub),

    # ── Chemical formulas + optional trailing ion charges ────────────────────
    (re.compile(r'(?<![A-Za-z_$\-])(?:[A-Z][a-z]?|[()\d]){2,}(?:[+-])?(?![_A-Za-z0-9])'),
     _chem_formula_sub),

    # ── Ion charges on simple elements: Cu2+, H+, Fe3+ ──────────────────────
    (re.compile(r'(\b[A-Z][a-z]?)(\d?[+-])(?=[\s,.:;()\[\]<>]|$)'), _ion_charge_sub),
]

_RULES = _SYMBOL_RULES


def _merge_math_blocks(text: str) -> str:
    """Merge adjacent math tokens and isolate isolated mathematical variables."""
    parts = []
    in_math = False
    for p in re.split(r'(\uE000|\uE001)', text):
        if p == '\uE000':
            in_math = True
            parts.append(p)
        elif p == '\uE001':
            in_math = False
            parts.append(p)
        elif not in_math:
            parts.append(re.sub(r'(?<![A-Za-z_])([xyzf])(?![A-Za-z_])', lambda m: f'\uE000{m.group(1)}\uE001', p))
        else:
            parts.append(p)
    text = ''.join(parts)

    text = text.replace('\uE001\uE000', ' ')
    text = re.sub(r'\uE001([ \d+\-/=,.\^\{\}<>]+)\uE000', r'\1', text)
    text = re.sub(r'\uE001([\d+\-/=,.\^\{\}<>]+)(?=$|[^a-zA-Z0-9])', lambda m: m.group(1) + '\uE001', text)
    text = re.sub(r'(^|[^a-zA-Z0-9])([\d+\-/=,.\^\{\}<>]+)\uE000', lambda m: m.group(1) + '\uE000' + m.group(2), text)
    return text


def _resolve_math(text: str) -> str:
    """Resolve \\uE000 and \\uE001 tokens into non-nested $...$ blocks."""
    text = _merge_math_blocks(text)
    
    res = []
    depth = 0
    for char in text:
        if char == '\uE000':
            if depth == 0:
                res.append('$')
            depth += 1
        elif char == '\uE001':
            depth -= 1
            if depth == 0:
                res.append('$')
        else:
            res.append(char)
    res_str = ''.join(res).replace('$$', '')
    # Prevent Pandoc tex_math_dollars rejection by trimming spaces directly inside the $ signs
    res_str = re.sub(r'\$(.*?)\$', lambda m: f"${m.group(1).strip()}$", res_str)
    # Clean up double backslashes before known LaTeX command names
    res_str = re.sub(
        r'\\\\(sin|cos|tan|sec|csc|cot|log|ln|exp|frac|sqrt|int|Delta|alpha|beta|gamma|pi|theta|lambda|mu)',
        r'\\\1',
        res_str
    )
    return res_str


_MATH_ITALIC_MAP = {}
for i in range(26):
    _MATH_ITALIC_MAP[0x1D44E + i] = ord('a') + i
    _MATH_ITALIC_MAP[0x1D434 + i] = ord('A') + i
_MATH_ITALIC_MAP[0x210E] = ord('h')


def auto_latex(text: str) -> str:
    """Apply auto-detection rules, avoiding nested $...$ crashes."""
    text = text.replace('\u2212', '-').replace('\u2013', '-')
    text = text.translate(_MATH_ITALIC_MAP)
    text = re.sub(r'\$(.*?)\$', lambda m: f'\uE000{m.group(1)}\uE001', text)

    for pat, repl in _STRUCTURAL_RULES:
        if callable(repl):
            text = pat.sub(repl, text)
        else:
            text = pat.sub(repl, text)

    for pat, repl in _SYMBOL_RULES:
        if callable(repl):
            text = pat.sub(repl, text)
        else:
            text = pat.sub(repl, text)

    text = re.sub(r"\s+([_^])", r"\1", text)
    text = re.sub(r"\s+\uE001([_^])", lambda m: "\uE001" + m.group(1), text)

    # Bare vector/unit-vector commands need a math-mode wrapper before they
    # reach Pandoc; otherwise the backslash sequence can be emitted as text.
    if ('\\vec{' in text or '\\hat{' in text) and '\uE000' not in text:
        text = f'\uE000{text.strip()}\uE001'

    return _resolve_math(text)


def text_needs_latex(text: str) -> bool:
    """Return True if auto_latex() would introduce any $...$ markers or if text already contains math symbols."""
    latex = auto_latex(text)
    complex_markers = ['\\frac', '\\int', '\\sum', '\\sqrt', 'matrix', '\\left', '\\right']
    return any(marker in latex for marker in complex_markers)


def latex_to_readable(text: str) -> str:
    """Convert the project's math notation to semantic Unicode for text PDFs.

    This is a compatibility adapter: fractions remain explicitly written as
    numerator/denominator and script positions use Unicode where available.
    """
    normalized = auto_latex(str(text or ""))
    normalized = _simplify_latex_for_pandoc(normalized)

    greek = {
        "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
        "epsilon": "ε", "varepsilon": "ε", "theta": "θ", "lambda": "λ",
        "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
        "phi": "φ", "omega": "ω", "Delta": "Δ", "Omega": "Ω",
    }
    operators = {
        "times": "×", "cdot": "·", "pm": "±", "leq": "≤", "geq": "≥",
        "neq": "≠", "infty": "∞", "int": "∫", "sum": "Σ", "prod": "Π",
    }
    for command, symbol in {**greek, **operators}.items():
        normalized = normalized.replace("\\" + command, symbol)
    normalized = re.sub(r"\s+([_^])", r"\1", normalized)
    normalized = re.sub(r"\\vec\{([^{}]+)\}", r"\1⃗", normalized)
    normalized = re.sub(r"\\hat\{([^{}]+)\}", r"\1̂", normalized)
    normalized = re.sub(r"\\text\{([^{}]*)\}|\\operatorname\{([^{}]*)\}",
                        lambda m: m.group(1) or m.group(2), normalized)
    normalized = re.sub(r"\\(?:left|right)", "", normalized)
    normalized = re.sub(r"\\begin\{(?:matrix|cases)\}|\\end\{(?:matrix|cases)\}", "", normalized)
    normalized = normalized.replace("&", " ").replace(r"\\", "; ")

    superscript_map = dict(zip("0123456789+-=()", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾"))
    subscript_map = dict(zip("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎"))

    def script_text(match, table, marker):
        value = match.group(1)
        if all(char in table for char in value):
            return "".join(table[char] for char in value)
        if marker == "_" and re.fullmatch(r"[A-Za-z0-9]+", value):
            return f"_{value}"
        return f"{marker}({value})"

    normalized = re.sub(r"\^\{([^{}]+)\}", lambda m: script_text(m, superscript_map, "^"), normalized)
    normalized = re.sub(r"_\{([^{}]+)\}", lambda m: script_text(m, subscript_map, "_"), normalized)
    normalized = re.sub(r"\\([A-Za-z]+)", lambda m: greek.get(m.group(1), operators.get(m.group(1), m.group(1))), normalized)
    normalized = normalized.replace("$", "").replace("{", "(").replace("}", ")")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


# ─────────────────────────────────────────────────────────────────────────────
# Block renderer: entire text → one tight-cropped PNG
# ─────────────────────────────────────────────────────────────────────────────

def _smart_wrap(text: str, chars_per_line: int) -> str:
    """Word-wrap text while keeping $...$ tokens unbreakable."""
    protected = re.sub(
        r'\$[^$]+?\$',
        lambda m: m.group(0).replace(' ', '\x00'),
        text
    )
    wrapped = textwrap.fill(protected, width=chars_per_line, break_long_words=False)
    return wrapped.replace('\x00', ' ')


def _find_matching_brace(s: str, start: int) -> int:
    """Find the index of the matching closing brace '}' starting at index s[start] which must be '{'."""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return -1

def _simplify_latex_for_pandoc(text: str) -> str:
    """Simplify LaTeX constructs that Pandoc cannot convert to plain text, handling arbitrary nesting."""
    while True:
        # Replace \frac{...}{...}
        idx = text.find('\\frac{')
        if idx != -1:
            start1 = idx + 5
            end1 = _find_matching_brace(text, start1)
            if end1 != -1 and end1 + 1 < len(text) and text[end1+1] == '{':
                start2 = end1 + 1
                end2 = _find_matching_brace(text, start2)
                if end2 != -1:
                    num = text[start1+1:end1]
                    den = text[start2+1:end2]
                    text = text[:idx] + f"({num})/({den})" + text[end2+1:]
                    continue
        
        # Replace \sqrt{...}
        idx = text.find('\\sqrt{')
        if idx != -1:
            start = idx + 5
            end = _find_matching_brace(text, start)
            if end != -1:
                inner = text[start+1:end]
                text = text[:idx] + f"√({inner})" + text[end+1:]
                continue
                
        # Replace \sqrt[...]{...}
        m = re.search(r'\\sqrt\[([^\]]+)\]\{', text)
        if m:
            idx = m.start()
            start = m.end() - 1
            end = _find_matching_brace(text, start)
            if end != -1:
                inner = text[start+1:end]
                n = m.group(1)
                text = text[:idx] + f"^{n}√({inner})" + text[end+1:]
                continue
                
        break
    return text

def to_math(text: str) -> str:
    r"""
    Format text for OMML math rendering via pandoc.
    1. Strip option labels if they accidentally leaked in.
    2. Remove existing '$' signs.
    3. Determine if it needs math rendering (contains \frac, \int, \sqrt, \sum, ^, _, \\).
    4. If it needs math, wrap the entire string in exactly one $...$ pair.
       Put words like 'Rate' inside \text{}.
    """
    # 1. Strip option label if accidentally present
    text = re.sub(r'^\s*\([A-Da-d]\)\s*', '', text)
    
    # 2. Remove all existing '$'
    text = text.replace('$', '')
    
    # 3. Does it need math?
    # We trigger math if we see LaTeX commands or superscripts/subscripts we injected
    math_triggers = ['\\frac', '\\int', '\\sqrt', '\\sum', '\\sin', '\\cos', '\\tan', '\\log', '\\ln', '\\operatorname', '^', '_']
    needs_math = any(trigger in text for trigger in math_triggers)
    
    if not needs_math:
        return text
        
    # 4. Math normalizations
    # Put words like 'Rate' in \text{}
    # Find continuous alphabetic words that are 2+ characters and not already a latex command
    # Actually, let's just target 'Rate' and similar words specifically if they appear
    text = re.sub(r'\b(Rate|rate)\b', r'\\text{\1}', text)
    
    # Fallback for ] 2 -> ]^{2}
    text = re.sub(r'\]\s*(\d)', r']^{\1}', text)
    
    # Add spacing around standard functions
    funcs = r'(sin|cos|tan|cot|sec|log|ln|lim|cosec)'
    text = re.sub(rf'(?<!\\)\b{funcs}\b', r'\\\1', text)
    text = re.sub(rf'\\{funcs}([a-df-zA-Z0-9])', r'\\\1 \2', text)
    
    # Clean up double spaces
    text = re.sub(r'  +', ' ', text).strip()
    
    # Finally, wrap in a single $...$ pair
    return f"${text}$"

# Alias for backwards compatibility with generate_pptx.py
render_math_text = auto_latex

def get_pandoc_text(text: str) -> str:
    """Render a text block to plain unicode text if needed."""
    if not _HAS_PANDOC: return text
    if '$' not in text and '\\' not in text: return text
    try:
        plain = pypandoc.convert_text(text, 'plain', format='latex', extra_args=['--wrap=none'])
        return plain.strip().replace('\r\n', '\n')
    except Exception as exc:
        warnings.warn(f"Math-to-text conversion failed; preserving the source expression: {exc!r}",
                      RuntimeWarning, stacklevel=2)
        return text

def render_text_block(*args, **kwargs) -> Path | None:
    return None

