"""
unmarked.py - find math in text that has NO $ markers, and the fixed English/math word test.

The extractor marks some math with $...$ and leaves the rest bare:
    "Find the value of ∫_{-1}^{1} x^{99} dx = (2026M)"      stem, no $
    "-(π)/(2)"   "secx+C"   "\\cosec^{-1}x+C"                options, no $
split_runs_auto() gives the same TEXT/MATH runs as split_question() for both cases.

    is_english(word)            fixed: second / since / tangent / secant are English, secx / sinx / xcosx are math
    mathish(token)              token looks like part of a formula
    looks_like_math(s)          the WHOLE string is a formula (typical option)
    split_unmarked(text)        -> [("TEXT"|"MATH", str)]
    split_runs_auto(text)       -> (tag, runs)       $-marked or bare
    suspect_swallowed(options)  labels whose text ends with a year tag = the next question was swallowed
"""
import re

from chem_convert import is_formula
from math_convert import INVISIBLE, TAG, split_question

FUNCS = ("sqrt", "arcsin", "arccos", "arctan", "cosec", "csc", "sin", "cos", "tan", "cot", "sec", "log", "ln", "exp", "lim")
_FUNC_RE = re.compile("|".join(FUNCS))
SHORT_EN = {"is", "of", "to", "in", "on", "at", "by", "or", "if", "as", "an", "be", "it", "we", "so", "no",
            "do", "he", "me", "my", "up", "us", "and", "the", "for", "are", "hence", "then", "with", "from",
            "that", "show", "find", "prove", "evaluate", "given", "let", "has", "have", "not", "also"}
OPS = set("+-−=*/|<>≤≥×÷^()∫√")
LABEL = re.compile(r"\((?:[A-Za-z]|[ivxIVX]+)\)|[A-Da-d][.)]")
_ALLOWED = re.compile(r"[A-Za-z0-9+\-−–—=*/|()<>≤≥×÷^_{}\[\]∫π√∞\\⁰¹²³⁴⁵⁶⁷⁸⁹ˣ]+")
STRONG = re.compile(r"[∫∑√π^]|_\{|sqrt\(|\)/\(|\\[A-Za-z]+")


def is_english(w: str) -> bool:
    lw = w.lower()
    if len(lw) == 1:
        return False
    if lw in SHORT_EN:
        return True
    if len(lw) == 2:
        return False                                   # dx, dt, xy
    if not _FUNC_RE.search(lw):
        return True                                    # 3+ letters, no function name
    # math only if the letters left between function names are single variables: secx, xcosx, sinxcosx
    return any(len(part) > 1 for part in _FUNC_RE.split(w))


def _split_punct(tok):
    m = re.fullmatch(r"(.*?)([.,;:]*)", tok, re.S)
    return m.group(1), m.group(2)


def mathish(tok: str) -> bool:
    core, _ = _split_punct(tok)
    if not core or LABEL.fullmatch(core):
        return False
    if any(is_english(w) for w in re.findall(r"[A-Za-z]+", core)):
        return False
    return _ALLOWED.fullmatch(core) is not None


def has_signal(seg: str) -> bool:
    return any(c in OPS for c in seg) or bool(_FUNC_RE.search(seg))


def is_strong(tok: str) -> bool:
    if STRONG.search(tok):
        return True
    return any(_FUNC_RE.search(w.lower()) and w.lower() not in FUNCS for w in re.findall(r"[A-Za-z]+", tok))


def _tokens(text):
    return re.findall(r"\s+|\S+", text)


def looks_like_math(s: str) -> bool:
    s = s.translate(INVISIBLE)
    toks = s.split()
    if not toks or not all(mathish(t) for t in toks) or not has_signal(s):
        return False
    # chemistry veto: NO2 + O2, CO2 + H2O must stay chemistry text
    return not any(len(w) >= 2 and is_formula(w) for t in toks for w in re.findall(r"[A-Za-z]+\d*", t))


def split_unmarked(text: str):
    text = text.translate(INVISIBLE)                 # invisible function-application sign U+2061
    if looks_like_math(text.strip()):
        return [("MATH", text.strip())]
    toks = []
    for t in _tokens(text):                            # sentence punctuation becomes its own token
        if t.isspace():
            toks.append(t)
            continue
        core, punct = _split_punct(t)
        if core:
            toks.append(core)
        if punct:
            toks.append(punct)
    n = len(toks)
    ok = [False] * n
    strong = [False] * n
    for i, t in enumerate(toks):
        if t.isspace() or (i == 0 and re.fullmatch(r"\d+[.)]", t)):
            continue                                   # a leading question number is never math
        ok[i] = mathish(t)
        strong[i] = ok[i] and is_strong(t)
    inside = [False] * n
    for i in range(n):
        if not strong[i]:
            continue
        j = i
        while j - 1 >= 0 and (toks[j - 1].isspace() or ok[j - 1]):
            j -= 1
        k = i
        while k + 1 < n and (toks[k + 1].isspace() or ok[k + 1]):
            k += 1
        while toks[j].isspace():
            j += 1
        while toks[k].isspace():
            k -= 1
        for x in range(j, k + 1):
            inside[x] = True
    runs, buf, kind = [], [], None
    for t, flag in zip(toks, inside):
        want = "MATH" if flag else "TEXT"
        if kind not in (None, want):
            runs.append((kind, "".join(buf)))
            buf = []
        kind = want
        buf.append(t)
    if buf:
        runs.append((kind, "".join(buf)))
    # whitespace between two MATH pieces belongs to the math
    return [(k, t if k == "TEXT" else t.strip()) for k, t in runs if t.strip() or k == "TEXT"]


def split_runs_auto(text: str):
    if "$" in text:
        return split_question(text)
    tag, m = None, TAG.search(text)
    if m:
        tag, text = m.group(1).replace(" ", ""), text[:m.start()]
    return tag, split_unmarked(text)


_STEMLIKE = re.compile(r"\?|\bwhich of the following\b|\b(?:evaluate|find|prove|show)\b", re.I)


def _looks_like_stem(body: str) -> bool:
    t = body.replace("$", " ").strip()
    return bool(_STEMLIKE.search(t)) or bool(re.search(r"(=|\bis|:)\s*$", t)) or \
        bool(re.search(r"∫", t) and re.search(r"\bd[xt]\b", t))


def option_tag_report(stem_tag, options: dict):
    """A year tag at the end of an option is either
         * the question's OWN tag written after option D (stem has none)   -> move it to the question
         * a swallowed NEXT question (the text before the tag looks like a stem) -> flag it, leave it alone
    -> (tag, cleaned_options, swallowed_labels)"""
    tag, cleaned, swallowed = stem_tag, {}, []
    for k, v in options.items():
        m = TAG.search(v)
        if not m:
            cleaned[k] = v
        elif _looks_like_stem(v[:m.start()]):
            cleaned[k] = v
            swallowed.append(k)
        else:
            cleaned[k] = v[:m.start()].rstrip()
            tag = tag or m.group(1).replace(" ", "")
    return tag, cleaned, swallowed


def suspect_swallowed(options: dict) -> list:
    return option_tag_report(None, options)[2]
