"""
chem_extra.py - subscripts written WITHOUT a space: CCl4, CH2Cl2, H2SO4, (CCl4), [N2O5], Na2CO3(aq).

    attached_subscripts(text) -> text      call it next to convert_chem() on TEXT runs only

Same safety rule as convert_chem: the token must parse as real element symbols. Extra guards:
no run of 3+ digits (years: UPSC2020), and no ALL-CAPS token of 4+ letters with digits only at the
end (acronyms: SSLC10). English words and exam names (Statement1, Class12, NEET2025, pH7) never parse.
"""
import re
from src.chem_convert import is_formula, SUB

_SPLIT = re.compile(r"(.*?)((?:\((?:g|l|s|aq)\))?[,.;:]*)", re.S)
_PAIRS = {"(": ")", "[": "]"}


def _tok(tok: str) -> str:
    body, tail = _SPLIT.fullmatch(tok).groups()
    lead = trail = ""
    if (len(body) > 2 and body[0] in _PAIRS and body[-1] == _PAIRS[body[0]]
            and body.count(body[0]) == 1 and body.count(body[-1]) == 1):
        lead, trail, body = body[0], body[-1], body[1:-1]
    if (re.search(r"(?<=[A-Za-z)])\d", body) and not re.search(r"\d{3,}", body)
            and not re.fullmatch(r"[A-Z]{4,}\d+", body) and is_formula(body)):
        body = re.sub(r"(?<=[A-Za-z)])(\d+)", lambda m: m.group(1).translate(SUB), body)
    return lead + body + trail + tail


def attached_subscripts(s: str) -> str:
    return re.sub(r"\S+", lambda m: _tok(m.group(0)), s)
