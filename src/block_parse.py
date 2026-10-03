"""
block_parse.py - subject-independent cleaning + question/option parsing for ONE question block.

    strip_noise(raw)  -> (text, chapter)   removes page headers, pictograms, math-italic letters
    parse_block(raw)  -> dict(stem, options, chapter, spill)

parse_block handles what the chemistry JSON shows:
  * "For: Boar d s" page header and "Chemical Kinetics:" chapter label inside the stem
  * an orphan "(D) ..." line BEFORE the question number (belongs to this question if it has no D,
    otherwise it is returned in `spill` for the previous question)
  * options written inline as "(A) ...", "A. ...", "A) ..." on their own lines, with wrapped lines
  * stray glyphs such as the envelope sign and 𝐾 (math italic K) -> K
"""
import re
import unicodedata

HEADERS = {"for:boards"}                    # compared with all spaces removed, lower-case
PICTO = re.compile("[\u2709\u2600-\u27BF\U0001F000-\U0001FAFF\uE000-\uF8FF]")
QNUM = re.compile(r"^\s*(\d+)\.\s")
OPT = re.compile(r"^\s*\(?([A-D])[\).]\s*(.*)$")
CHAPTER = re.compile(r"[A-Z][A-Za-z ,&\-]{2,60}:")


def fold_math_alnum(s: str) -> str:
    """𝐾 -> K, 𝑥 -> x. Only the Mathematical Alphanumeric block, so ², ₂, ½ are NOT touched."""
    return "".join(unicodedata.normalize("NFKC", c) if 0x1D400 <= ord(c) <= 0x1D7FF else c for c in s)


def strip_noise(raw: str):
    text = fold_math_alnum(PICTO.sub("", raw))
    lines = text.split("\n")
    qi = next((i for i, l in enumerate(lines) if QNUM.match(l)), len(lines))
    chapter, out = None, []
    for i, ln in enumerate(lines):
        if re.sub(r"\s+", "", ln).lower() in HEADERS:
            continue
        # chapter labels only count BEFORE the question number, so a stem line such as
        # "Identify the correct statement:" is never dropped
        if i < qi and CHAPTER.fullmatch(ln.strip()) and not re.search(r"\d", ln):
            chapter = ln.strip().rstrip(":")
            continue
        out.append(ln)
    return "\n".join(out).strip(), chapter


def parse_block(raw: str) -> dict:
    text, chapter = strip_noise(raw)
    lines = [l for l in text.split("\n")]
    qi = next((i for i, l in enumerate(lines) if QNUM.match(l)), None)
    if qi is None:
        return {"stem": text, "options": {}, "chapter": chapter, "spill": {}}

    orphans = {}
    for l in lines[:qi]:
        m = OPT.match(l)
        if m:
            orphans[m.group(1)] = m.group(2).strip()

    stem, options, last, expect = [], {}, None, "A"
    for l in lines[qi:]:
        m = OPT.match(l)
        if m and m.group(1) == expect:                            # next option in order A, B, C, D
            last = m.group(1)
            options[last] = m.group(2).strip()
            expect = chr(ord(expect) + 1)
        elif last is not None and l.strip():                      # wrapped option line
            options[last] += " " + l.strip()
        elif last is None and l.strip():
            stem.append(l.rstrip())

    spill = {}
    for k, v in orphans.items():
        if k in options:
            spill[k] = v                                          # belongs to the previous question
        else:
            options[k] = v
    return {"stem": "\n".join(stem), "options": dict(sorted(options.items())),
            "chapter": chapter, "spill": spill}
