"""
headings.py - section headings that get glued onto the wrong text.

    is_heading(text)                 "Solutions", "Chemical Kinetics"  (a divider), never "Integrate $∫ f$ (2023)"
    strip_trailing_heading(text)     "Cl 2 Application Based Questions:" -> ("Cl 2", "Application Based Questions")
                                     a chapter label at the end of the LAST option belongs to the NEXT block
"""
import re

from math_convert import TAG

_TAIL = re.compile(r"^(?P<body>.*?\S)\s+(?P<head>(?:[A-Z][a-z]+(?:\s+|-)){0,5}[A-Z][a-z]+)\s*:\s*$", re.S)


def is_heading(text: str) -> bool:
    t = text.strip()
    return bool(t) and len(t.split()) <= 4 and t[0].isalpha() and t[0].isupper() \
        and not re.search(r"[$\d∫∑√=^()?:]", t) and not TAG.search(t) and not t.startswith("[IMG")


def strip_trailing_heading(text: str):
    m = _TAIL.match(text.strip())
    if not m:
        return text, None
    return m.group("body"), m.group("head")
