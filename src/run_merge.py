"""
run_merge.py - glue the pieces of ONE expression back together before conversion.

The extractor wraps each fraction / root in its own $...$ and leaves the connecting operators outside:
    $(X)/(2)$ $sqrt(1+X^{2})$ +$(1)/(2)$ log|𝑥 +$sqrt(1+X^{2})$| + 𝐶
split_question() turns that into 7 runs, which would render as 4 separate equations with plain text
in between. merge_runs() rebuilds a single MATH run.

    merge_runs(runs) -> runs      runs = [("TEXT", str) | ("MATH", str), ...]   (raw, before convert_math)

Rules
  * fold math-italic letters first (𝑥 -> x, 𝐶 -> C)
  * MATH + whitespace-only TEXT + MATH  -> one MATH
  * a TEXT run next to a MATH run gives its math-looking edge to the MATH run, but only if that edge
    contains an operator/bracket or a function name, and stops at the first English word
  * labels like (a), (ii), A. are never treated as math; punctuation-only TEXT (", ") never glues
"""
import re
from src.block_parse import fold_math_alnum

from src.unmarked import FUNCS, OPS, SHORT_EN, LABEL, is_english, mathish, has_signal, _split_punct, _FUNC_RE


def _tokens(text):
    return re.findall(r"\s+|\S+", text)


def peel_prefix(text):
    """-> (math_prefix, rest)."""
    toks, taken, i = _tokens(text), [], 0
    while i < len(toks):
        t = toks[i]
        if t.isspace():
            taken.append(t); i += 1; continue
        if not mathish(t):
            break
        core, punct = _split_punct(t)
        taken.append(core)
        if punct:                                      # sentence punctuation ends the math
            return _finish(taken, punct + "".join(toks[i + 1:]), text)
        i += 1
    return _finish(taken, "".join(toks[i:]), text)


def _finish(taken, rest, text):
    seg = "".join(taken).strip()
    if not seg or not has_signal(seg):
        return "", text
    trailing_ws = "".join(taken)[len("".join(taken).rstrip()):]
    return seg, trailing_ws + rest


def peel_suffix(text):
    """-> (rest, math_suffix)."""
    toks = _tokens(text)
    i = len(toks)
    while i > 0:
        t = toks[i - 1]
        if t.isspace():
            i -= 1
            continue
        if _split_punct(t)[1] or not mathish(t):       # trailing punctuation = sentence boundary
            break
        i -= 1
    while i < len(toks) and toks[i].isspace():           # keep the space before the formula in the TEXT
        i += 1
    seg = "".join(toks[i:]).strip()
    if not seg or not has_signal(seg):
        return text, ""
    return "".join(toks[:i]), seg


def merge_runs(runs):
    runs = [(k, fold_math_alnum(t)) for k, t in runs]
    out, pending = [], ""
    for i, (kind, text) in enumerate(runs):
        if kind == "MATH":
            if pending:
                text, pending = pending + " " + text, ""
            if out and out[-1][0] == "MATH":
                out[-1][1] += " " + text
            else:
                out.append(["MATH", text])
            continue
        prev_math = bool(out) and out[-1][0] == "MATH"
        next_math = i + 1 < len(runs) and runs[i + 1][0] == "MATH"
        if prev_math:
            lead, text = peel_prefix(text)
            if lead:
                out[-1][1] += " " + lead
        if next_math and text.strip():
            text, trail = peel_suffix(text)
            pending = trail
        if text.strip():
            out.append(["TEXT", text])
        elif not (prev_math and next_math) and text and out and out[-1][0] == "TEXT":
            out[-1][1] += text
    if pending:                                         # cannot happen (suffix only set before MATH), safety net
        out.append(["TEXT", pending])
    return [(k, t) for k, t in out]
