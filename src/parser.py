"""Regex-based universal question parser — works for any subject.

Takes a flat list of text lines (from extract_pdf or extract_docx)
and turns them into structured question dicts with:
  id, section, question, options{A/B/C/D}, answer, parsed_ok, question_type

question_type values:
  "mcq"              — has 4 options A/B/C/D
  "match_the_column" — match-the-column MCQ variant
  "open"             — short-answer / long-answer (no options, parsed_ok=True)

Section detection is AUTOMATIC — no hardcoded subject names.
Marks headers like "1 Marks", "2 Marks" etc. are detected automatically.
"""
from __future__ import annotations

import re
import sys


# ── Section-header detection ───────────────────────────────────────────────────

_Q_NUM_RE = re.compile(r'^\d+\.(?!\d)\s*')
_OPTION_LABEL_RE = re.compile(r'^(?:\([A-Da-d]\)|(?<!-)[A-Da-d][.)]\s)', re.IGNORECASE)

# Mark-style headers: "1 Marks", "2 Marks", "3 Marks", "5 Marks", "6 Marks", "1 Marks (FIB)"
_MARKS_HEADER_RE = re.compile(r'^\d+\s+[Mm]arks?(\s*\(.*?\))?\s*$', re.IGNORECASE)
_KNOWN_SECTION_HEADERS_RE = re.compile(
    r'^(?:MCQs?|MCQ[’\']s|Fill in the blanks?(\s*\(.*?\))?|FIB|'
    r'Match the (?:following|column)|Assertion and Reason|'
    r'Very Short Answer Questions?|Short Answer Questions?|Long Answer Questions?|'
    r'Section\s+[A-Z\d]+|Part\s+[A-Z\d]+)\s*$',
    re.IGNORECASE
)

# Noise lines to skip (ads, course promos, etc.)
_NOISE_PATTERNS = [
    re.compile(r'\b(Crash Course|DPPs|PYQs|Mentorship|Doubt Sessions|Concept videos)\b', re.I),
    re.compile(r'^Join\b', re.I),
    re.compile(r'^Live\b', re.I),
    re.compile(r'^Personal\b', re.I),
    re.compile(r'What you get on our app', re.I),
    re.compile(r'Lecture pdfs and Hand written notes', re.I),
    re.compile(r'In app chat feature', re.I),
    re.compile(r'Paid Courses', re.I),
    re.compile(r'Detailed [Ee]xplanation (?:for|of) every topic', re.I),
    re.compile(r'Download our app', re.I),
    re.compile(r'Subscribe to our', re.I),
    re.compile(r'Telegram channel', re.I),
    re.compile(r'WhatsApp group', re.I),
    re.compile(r'YouTube channel', re.I),
    re.compile(r'Follow us on', re.I),
]

_NON_SECTION_STARTERS = re.compile(
    r'^(?:Define|State|Explain|Evaluate|Find|Integrate|Calculate|Prove|Show|Verify|Determine|Solve|Write|Give|Name|Mention):?$',
    re.IGNORECASE
)


def _is_noise(line: str) -> bool:
    """True if this line is advertising/noise that should be skipped."""
    for pat in _NOISE_PATTERNS:
        if pat.search(line):
            return True
    return False


def _is_section_header(line: str) -> bool:
    """Heuristic: is this line a section/chapter header?"""
    stripped = line.strip()
    if _MARKS_HEADER_RE.match(stripped) or _KNOWN_SECTION_HEADERS_RE.match(stripped):
        return True
    if len(stripped) < 3 or len(stripped) > 80:
        return False
    if re.match(r'^\d+\.?$', stripped):
        return False
    if _NON_SECTION_STARTERS.match(stripped):
        return False
    if _Q_NUM_RE.match(stripped):
        return False
    if _OPTION_LABEL_RE.match(stripped):
        return False
    if re.match(r'^(Column\s+[IVX]+|[IVX]+):?$', stripped, re.IGNORECASE):
        return False

    words = stripped.split()
    if not words:
        return False

    if words[-1].lower() in ('is', 'are', 'be', 'of', 'the', 'for', 'a', 'an', 'as', 'to', 'in', 'on', 'with', 'from', 'by', 'at'):
        return False
    if stripped.endswith('?') or stripped.endswith('.') or stripped.endswith(','):
        return False

    significant_words = [w for w in words if w.lower() not in ('and', 'or', 'of', 'the', 'in', 'for', 'to', 'with')]
    if not significant_words:
        return False

    upper_words = sum(1 for w in significant_words if w[0].isupper() or w.isdigit())
    ratio = upper_words / len(significant_words)
    return ratio >= 0.7 and len(words) <= 10


def _is_open_section_header(line: str) -> bool:
    """True if this header introduces open/short-answer questions."""
    stripped = line.strip()
    if _MARKS_HEADER_RE.match(stripped):
        return True
    if re.search(r'Fill in the blanks?|FIB|Short Answer|Very Short Answer|Long Answer', stripped, re.I):
        return True
    return False


# Matches:
# 1) ({L}) - parenthesized: can follow whitespace, punctuation, math, token, but not hyphen -(A)
# 2) {L}. - period format: must not be preceded by letter/digit/- and must be followed by whitespace or end
# 3) {L}) - single paren format: must not be preceded by letter/digit/(/- and must be followed by whitespace or end
OPTION_RE_TEMPLATE = r"(?:(?<!-)\({L}\)|(?<![a-zA-Z0-9-])\b{L}\.(?=\s|$)|(?<![a-zA-Z0-9(-])\b{L}\)(?=\s|$))\s*"

_PAIRING_RE = re.compile(
    r'\(\d\)\s*-\s*\([A-Da-d]\)'
    r'|\b\d\s*-\s*[A-D]\b'
    r'|\b(?:i{1,3}|iv|v|vi)\s*-\s*[a-d]\b',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Open/short-answer question detection
# ---------------------------------------------------------------------------

_OPEN_Q_STARTERS = re.compile(
    r'^\s*(?:Evaluate|Find|Integrate|Prove(?: that)?|Show(?: that)?|'
    r'Verify|Calculate|Derive|State|Define|Explain|Determine|Solve|'
    r'Write|Express|Expand|Simplify|If\b|Let\b|Fill\b|Mention\b|How\b|What\b|Why\b|When\b|Where\b|Name\b|Which\b|Give\b|Draw\b|Deduce\b|Differentiate\b)',
    re.IGNORECASE
)

_INCOMPLETE_ENDINGS = (
    ':', ',', 'and', 'with', 'where', 'to', 'of', 'for', 'in', 'is', 'are', 'that',
    'find', 'evaluate', 'calculate', 'determine', 'such that', 'given by', 'as'
)

_YEAR_RE = re.compile(r'\(\d{4}[^\)]*\)\.?\s*$')


def _looks_like_open_question(text: str) -> bool:
    return bool(_OPEN_Q_STARTERS.match(text.strip()))


# ---------------------------------------------------------------------------
# Match-the-column aware option finder
# ---------------------------------------------------------------------------

def _find_match_column_positions(text: str) -> dict | None:
    keys = list("ABCD")

    all_matches: dict[str, list[re.Match]] = {}
    for letter in keys:
        pat = re.compile(OPTION_RE_TEMPLATE.format(L=letter), re.IGNORECASE)
        all_matches[letter] = list(pat.finditer(text))

    if not all(all_matches[l] for l in keys):
        return None

    for a_match in all_matches["A"]:
        lookahead = text[a_match.end(): a_match.end() + 25]
        if not _PAIRING_RE.search(lookahead):
            continue
        positions: dict[str, tuple[int, int]] = {"A": (a_match.start(), a_match.end())}
        search_from = a_match.end()
        for letter in "BCD":
            pat = re.compile(OPTION_RE_TEMPLATE.format(L=letter), re.IGNORECASE)
            m = pat.search(text, search_from)
            if not m:
                break
            positions[letter] = (m.start(), m.end())
            search_from = m.end()
        if len(positions) == 4:
            return positions
    return None


# ---------------------------------------------------------------------------
# Core parsing logic
# ---------------------------------------------------------------------------

def split_questions(lines: list[str]) -> list[dict]:
    """Group lines into per-question blocks.
    Handles numbered MCQs, unnumbered MCQs, and open-answer sections.
    Generates sequential global IDs in document order.
    """
    blocks = []
    cur = None
    current_section = None
    in_open_section = False
    global_id = 1

    opt_d_pat = re.compile(OPTION_RE_TEMPLATE.format(L="[Dd]"), re.IGNORECASE)
    opt_a_pat = re.compile(OPTION_RE_TEMPLATE.format(L="[Aa]"), re.IGNORECASE)
    opt_bcd_pat = re.compile(OPTION_RE_TEMPLATE.format(L="[B-Db-d]"), re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_noise(stripped):
            continue

        if _is_section_header(stripped):
            if cur:
                blocks.append(cur)
                cur = None
            current_section = stripped.rstrip(':').strip()
            in_open_section = _is_open_section_header(stripped)
            continue

        # Check numbered question (avoid matching decimal numbers like "0.413")
        m_num = re.match(r"^(\d+)(?:\.(?!\d)|\))\s*(.*)$", stripped)
        is_num_q = False
        m_text = stripped

        if m_num:
            is_num_q = True
            m_text = m_num.group(2)

        is_unnum = False
        if not is_num_q:
            text_so_far = " ".join(cur["lines"]) if cur else ""
            m_d = opt_d_pat.search(text_so_far) if cur else None
            
            if m_d:
                opt_d_content = text_so_far[m_d.end():].strip()
                is_option_label = bool(opt_bcd_pat.match(stripped))
                is_answer_or_sol = stripped.lower().startswith(('answer', 'sol', 'hint'))
                is_pairing = bool(_PAIRING_RE.search(stripped))

                if opt_d_content and not is_option_label and not is_answer_or_sol and not is_pairing:
                    if opt_a_pat.search(stripped):
                        is_unnum = True
                    elif _YEAR_RE.search(text_so_far):
                        is_unnum = True
                    elif len(stripped) >= 4 and (re.match(r'^[\$A-Z\u222b\u221a\u2211\u0391-\u03c9"\'(]', stripped) or bool(_OPEN_Q_STARTERS.match(stripped))):
                        is_unnum = True
                    elif re.search(r'\b\d{4}M\b', stripped, re.I) or re.match(r'^Question\s+\d+', stripped, re.I):
                        is_unnum = True
                        
            if not is_unnum:
                if in_open_section:
                    if not cur:
                        is_unnum = True
                    else:
                        prev_text = " ".join(cur["lines"]).strip()
                        prev_ends_incomplete = bool(re.search(r'\b(?:is|are|of|for|to|with|where|in|by|given by|that|following|find|evaluate|calculate|determine)\s*(?:\(\d{4}[^\)]*\))?\.?\s*$', prev_text, re.I))

                        cur_has_roman = any(re.match(r'^\s*(?:\([iIvVxX]+\)|[iIvVxX]+[.)]\s)', l) for l in cur["lines"])
                        cur_has_letter = any(re.match(r'^\s*(?:\([a-zA-Z]\)|[a-zA-Z][.)]\s)', l) for l in cur["lines"])

                        new_is_roman = bool(re.match(r'^\s*(?:\([iIvVxX]+\)|[iIvVxX]+[.)]\s)', stripped))
                        new_is_letter = bool(re.match(r'^\s*(?:\([a-zA-Z]\)|[a-zA-Z][.)]\s)', stripped))

                        is_subpart_continuation = (cur_has_roman and new_is_roman) or (cur_has_letter and new_is_letter)
                        is_subpart_transition = ((cur_has_roman and new_is_letter) or (cur_has_letter and new_is_roman)) and not is_subpart_continuation

                        is_subitem = is_subpart_continuation or bool(re.match(r'^\s*\b(?:Strictly|Part|Case)\b', stripped, re.I))

                        if is_subpart_transition:
                            if not opt_a_pat.match(stripped) and not opt_bcd_pat.match(stripped):
                                is_unnum = True
                        elif _YEAR_RE.search(prev_text):
                            if not is_subpart_continuation and not (is_subitem and prev_ends_incomplete):
                                if not opt_a_pat.match(stripped) and not opt_bcd_pat.match(stripped):
                                    is_unnum = True
                        elif bool(_OPEN_Q_STARTERS.match(stripped)):
                            prev_had_question = bool(re.search(r'\?|\b(?:Evaluate|Find|Integrate|Prove|Show|Verify|Calculate|Derive|State|Define|Explain|Determine|Solve|Write|Mention)\b', prev_text, re.I))
                            last_line = cur["lines"][-1].strip().lower()
                            if prev_had_question and not any(last_line.endswith(inc) for inc in _INCOMPLETE_ENDINGS) and not is_subitem:
                                is_unnum = True
                else:
                    # MCQ section logic (without Option D, which we already handled)
                    if not cur:
                        if not opt_a_pat.match(stripped) and not opt_bcd_pat.match(stripped) and not stripped.lower().startswith(('answer', 'sol')):
                            is_unnum = True

        if is_num_q or is_unnum:
            if cur:
                blocks.append(cur)
            cur = {
                "id":              global_id,
                "section":         current_section,
                "lines":           [m_text] if m_text else [],
                "in_open_section": in_open_section,
            }
            global_id += 1
        elif cur:
            cur["lines"].append(stripped)

    if cur:
        blocks.append(cur)
    return blocks



def clean_noise(text: str) -> str:
    text = re.sub(r'For:\s*Boar\s*d\s*s|For:\s*Boards', '', text, flags=re.IGNORECASE)
    text = re.sub(r'✉.*?(\n|$)', '', text, flags=re.IGNORECASE)
    return text.strip()


def _extract_options(text: str, positions: dict) -> dict[str, str]:
    keys = list("ABCD")
    options = {}
    for i, letter in enumerate(keys):
        end = positions[keys[i + 1]][0] if i < 3 else len(text)
        opt_text = text[positions[letter][1]: end].strip()
        if '\n' in opt_text:
            opt_text = " ".join(line.strip() for line in opt_text.split('\n') if line.strip())
        options[letter] = opt_text
    return options


def parse_block(block: dict) -> dict:
    """Parse one block into a structured question dict.

    Open-answer blocks: parsed_ok=True, question_type='open'.
    MCQ blocks: parsed_ok=True if 4 options found, else False.
    """
    text = "\n".join(block["lines"])
    text = clean_noise(text)
    in_open = block.get("in_open_section", False)

    result = {
        "id":        block["id"],
        "section":   block["section"],
        "question":  None,
        "options":   {},
        "answer":    None,
        "parsed_ok": False,
    }

    # ── Match-the-column check ────────────────────────────────────────────
    mc_positions = _find_match_column_positions(text)
    if mc_positions:
        mc_question = text[: mc_positions["A"][0]].strip()
        mc_options = _extract_options(text, mc_positions)
        if mc_question and all(mc_options.values()):
            result["question"]      = re.sub(r'^(?:Q\s*)?\d+[\.\)]\s*', '', mc_question, flags=re.IGNORECASE)
            result["options"]       = mc_options
            result["parsed_ok"]     = True
            result["question_type"] = "match_the_column"
            return result

    # ── MCQ parsing ───────────────────────────────────────────────────────
    positions: dict[str, tuple[int, int]] = {}
    search_from = 0
    for letter in "ABCD":
        pattern = re.compile(OPTION_RE_TEMPLATE.format(L=letter), re.IGNORECASE)
        match = pattern.search(text, search_from)
        if not match:
            break
        positions[letter] = (match.start(), match.end())
        search_from = match.end()

    if len(positions) != 4:
        # ── Open/short-answer fallback ────────────────────────────────────────
        if in_open or _looks_like_open_question(text):
            result["question"]      = re.sub(r'^(?:Q\s*)?\d+[\.\)]\s*', '', text.strip(), flags=re.IGNORECASE)
            result["question_type"] = "open"
            result["parsed_ok"]     = True
            return result
        
        words = text.strip().split()
        from src.headings import is_heading
        if is_heading(text.strip()):
            result["question"] = text.strip().rstrip(':').strip()
            result["question_type"] = "divider"
            result["id"] = None
            result["parsed_ok"] = True
            return result
            
        result["question"] = re.sub(r'^(?:Q\s*)?\d+[\.\)]\s*', '', text.strip(), flags=re.IGNORECASE)
        return result

    question = text[: positions["A"][0]].strip()
    options = _extract_options(text, positions)

    if bool(re.search(r'\([A-Da-d]\)', options.get("D", ""))):
        result["parsed_ok"] = False
        return result

    if not question or any(not v for v in options.values()):

        result["question"] = text.strip()
        return result

    result["question"]      = question
    result["options"]       = options
    result["question_type"] = "mcq"
    result["parsed_ok"]     = True
    
    if result.get("question"):
        result["question"] = re.sub(r'^(?:Q\s*)?\d+[\.\)]\s*', '', result["question"], flags=re.IGNORECASE)

    last_opt = list(result["options"].keys())[-1]
    opt_text = result["options"][last_opt]
    from src.headings import strip_trailing_heading
    clean_opt, heading = strip_trailing_heading(opt_text)
    if heading:
        print(f"DEBUG: suffix={heading}, prefix={clean_opt}")
        result["options"][last_opt] = clean_opt
        divider = {
            "question_type": "divider",
            "question": heading,
            "id": None,
            "parsed_ok": True
        }
        return [result, divider]

    return result


def parse_all(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """Returns (parsed, failed)."""
    blocks = split_questions(lines)
    parsed, failed = [], []
    for b in blocks:
        rs = parse_block(b)
        if not isinstance(rs, list): rs = [rs]
        for r in rs:
            if r["parsed_ok"]:
                parsed.append(r)
            else:
                failed.append(b)
    return parsed, failed


if __name__ == "__main__":
    import json as _json

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    if len(sys.argv) < 2:
        sys.exit("Usage: python -m src.parser <input.pdf|input.docx>")

    _path = sys.argv[1]
    if _path.endswith(".pdf"):
        try:
            from src.extract_pdf import extract_lines
        except ModuleNotFoundError:
            from extract_pdf import extract_lines  # type: ignore[no-redef]
    elif _path.endswith(".docx"):
        try:
            from src.extract_docx import extract_lines
        except ModuleNotFoundError:
            from extract_docx import extract_lines  # type: ignore[no-redef]
    else:
        sys.exit("Unsupported file type. Use .pdf or .docx")

    _parsed, _failed = parse_all(extract_lines(_path))
    mcqs  = [q for q in _parsed if q.get("question_type") in ("mcq", "match_the_column")]
    opens = [q for q in _parsed if q.get("question_type") == "open"]
    print(f"Parsed OK: {len(_parsed)}  (MCQ: {len(mcqs)}, Open/SA: {len(opens)})  |  Needs review: {len(_failed)}")
    if _failed:
        print("Failed IDs:", [b["id"] for b in _failed])

    if len(sys.argv) > 2:
        out_path = sys.argv[2]
        with open(out_path, 'w', encoding='utf-8') as f:
            _json.dump(_parsed, f, indent=2, ensure_ascii=False)
        print(f"Saved parsed output to {out_path}")
