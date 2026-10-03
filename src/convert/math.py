"""
math_convert.py - drop-in converter for MATH runs only (mcq2slides).

Public API
    split_question(q)   -> (tag, runs)      runs = [("TEXT", str) | ("MATH", str), ...]
    convert_math(s)     -> LaTeX string      (input = contents of one MATH run, no $ signs)
    check_math(latex)   -> list[str]         problems; empty list = OK

Never call convert_math on TEXT or CHEM runs.
"""
import re

# ---------------------------------------------------------------- cleaning
INVISIBLE = dict.fromkeys(map(ord, "\u2061\u2062\u2063\u2064\u200b\u200c\u200d\ufeff"), None)

SYMBOLS = {
    "∫": r"\int ", "π": r"\pi ", "∑": r"\sum ", "±": r"\pm ", "×": r"\times ",
    "∞": r"\infty ", "≤": r"\le ", "≥": r"\ge ", "≠": r"\ne ", "→": r"\to ",
}

FUNC = re.compile(r"\\?(arcsin|arccos|arctan|cosec|sin|cos|tan|cot|sec|log|ln)")
# doubled tokens from the PDF text layer: "sec sec x", "loglog sinx"
DOUBLE = re.compile(
    r"(?<![A-Za-z])(arcsin|arccos|arctan|cosec|csc|sin|cos|tan|cot|sec|log|ln)\s*\1(?![A-Za-z]{2})"
)


def collapse_doubles(s: str) -> str:
    return DOUBLE.sub(r"\1", s)


def fix_functions(s: str) -> str:
    """One pass. cosec -> \\operatorname{cosec}; sin, cos, ... -> \\sin , \\cos , ...
    Run it on MATH runs only. Text inside \\text{} / \\operatorname{} must be stashed first
    (convert_math does this)."""
    def repl(m):
        n = m.group(1)
        return r"\operatorname{cosec} " if n == "cosec" else "\\" + n + " "
    return FUNC.sub(repl, s)


# ---------------------------------------------------------------- structure
def _match_left(s, close):
    d = 0
    for i in range(close, -1, -1):
        d += (s[i] == ")") - (s[i] == "(")
        if d == 0:
            return i
    return -1


def _match_right(s, open_):
    d = 0
    for i in range(open_, len(s)):
        d += (s[i] == "(") - (s[i] == ")")
        if d == 0:
            return i
    return -1


def sqrt_to_latex(s: str) -> str:
    while (k := s.find("sqrt(")) != -1:
        b = _match_right(s, k + 4)
        if b < 0:
            break
        s = s[:k] + "\\sqrt{" + s[k + 5:b] + "}" + s[b + 1:]
    return s


def linear_fractions(s: str) -> str:
    """Word 'linear format' (a)/(b) -> \\frac{a}{b}. Handles nested brackets."""
    while (k := s.find(")/(")) != -1:
        a = _match_left(s, k)
        b = _match_right(s, k + 2)
        if a < 0 or b < 0:
            break
        s = s[:a] + "\\frac{" + s[a + 1:k] + "}{" + s[k + 3:b] + "}" + s[b + 1:]
    return s


# ---------------------------------------------------------------- piecewise
IF = re.compile(r",?\s*\bif\b\s*")


def split_condition(c: str) -> str:
    c = re.sub(r"\b([fgh])\s+\(", r"\1(", c)          # "f (x)"   -> "f(x)"
    c = re.sub(r"\)\s*(is|are)\b", r") \1", c)         # "f(x)is"  -> "f(x) is"
    m = re.search(r"\s+(is|are)\b.*$", c)
    if m:                                              # words go to \text{}, space kept inside
        return c[:m.start()].strip() + "\\text{" + m.group(0).rstrip() + "}"
    return c.replace(" ", "")


def piecewise_to_cases(s: str) -> str:
    """'A = {V1, if C1  V2, if C2'  ->  A = \\begin{cases} V1 & \\text{if } C1 \\\\ V2 & ... \\end{cases}
    Returns s unchanged when it cannot split safely (caller sends it to review)."""
    # Fix a: Cut the sentence from a formula before piecewise conversion
    m_split = re.search(r"\s+\b(and hence|hence|then)\b", s, re.IGNORECASE)
    tail = ""
    if m_split:
        tail = s[m_split.start():]
        s = s[:m_split.start()]
        
    m = re.search(r"=\s*\{", s)
    if not m:
        return s + tail
    head, body = s[:m.start()].strip(), s[m.end():].strip()
    if body.endswith("}") and body.count("}") > body.count("{"):
        body = body[:-1].strip()
    ifs = list(IF.finditer(body))
    if len(ifs) < 2:
        return s + tail
    values = [body[:ifs[0].start()].strip()]
    conds = []
    for i, f in enumerate(ifs):
        end = ifs[i + 1].start() if i + 1 < len(ifs) else len(body)
        seg = body[f.end():end].strip()
        if i + 1 < len(ifs):
            parts = seg.rsplit(None, 1)                # last token before the next "if" = next value
            if len(parts) < 2:
                return s + tail
            seg, nxt = parts
            values.append(nxt.rstrip(","))
        conds.append(split_condition(seg))
    rows = [f"{v} & \\text{{if }} {c}" for v, c in zip(values, conds)]
    return f"{head} = \\begin{{cases}} " + " \\\\ ".join(rows) + " \\end{cases}" + tail


# ---------------------------------------------------------------- main entry
def convert_math(s: str) -> str:
    s = s.translate(INVISIBLE).strip().strip("$").strip()
    s = collapse_doubles(s)
    s = piecewise_to_cases(s)

    keep = []                                          # protect \text{..} and \operatorname{..}
    def stash(m):
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"
    s = re.sub(r"\\(?:text|operatorname)\{[^}]*\}", stash, s)

    s = sqrt_to_latex(s)
    s = linear_fractions(s)
    for k, v in SYMBOLS.items():
        s = s.replace(k, v)
    s = fix_functions(s)
    s = re.sub(r"(?<!\\,)\.?\s*\bd([xt])\b", r"\\,d\1", s)   # ".dx" / " dx" -> "\,dx"
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([}^_])", r"\1", s)                # no space before } ^ _
    s = re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], s)
    return s.strip()


# ---------------------------------------------------------------- validation
_BR = r"\{(?:[^{}]|\{[^{}]*\})*\}"


def check_math(latex: str) -> list:
    problems = []
    if latex.count("{") != latex.count("}"):
        problems.append("unbalanced braces")
    if latex.count("\\begin") != latex.count("\\end"):
        problems.append("begin/end mismatch")
    n_int = len(re.findall(r"\\int(?![A-Za-z])", latex))
    n_d = len(re.findall(r"\\,d[xt]\b", latex))
    if n_int != n_d:
        problems.append(f"{n_int} integral sign(s) but {n_d} differential(s)")
    if re.search(r"\\int(?:_" + _BR + r")?(?:\^" + _BR + r")?\s*\\,d[xt]", latex):
        problems.append("integral with empty integrand")
    return problems


# ---------------------------------------------------------------- run splitting
TAG = re.compile(
    r"\s*\(\s*(\d{4}[A-Za-z]?(?:-\d)?(?:\s*,\s*\d{4}[A-Za-z]?(?:-\d)?)*)\s*\)\s*$"
)


FUNCS = {"arcsin", "arccos", "arctan", "cosec", "csc", "sin", "cos", "tan", "cot", "sec", "log", "ln"}

def split_question(q: str):
    """-> (tag or None, runs). Splits at $...$, trims spaces inside the $ pair, pulls the trailing
    year tag "(2014,2015s,2019)" out of the stem, and re-attaches a bare 'dx' left outside the math."""
    tag = None
    m = TAG.search(q)
    if m:
        tag, q = m.group(1).replace(" ", ""), q[:m.start()]
    runs, pos = [], 0
    for m in re.finditer(r"\$(.+?)\$", q, re.S):
        if m.start() > pos:
            runs.append(["TEXT", q[pos:m.start()]])
        runs.append(["MATH", m.group(1).strip()])
        pos = m.end()
    if pos < len(q):
        runs.append(["TEXT", q[pos:]])
    out = []
    for kind, text in runs:
        if kind == "TEXT" and out and out[-1][0] == "MATH" and re.fullmatch(r"\s*d[xt]\s*", text):
            out[-1][1] += " " + text.strip()
        else:
            out.append([kind, text])
            
    # "insert a space between a TEXT run and the next MATH run if the TEXT does not end with one"
    return tag, [(k, t) for k, t in out if t.strip()]

