"""
chem_convert.py - chemistry text fixes for mcq2slides.

PDF text layers write subscripts/superscripts as separate tokens: "ZnSO 4", "O 2 (g)", "[NO] 2",
"[R 0 ]", "Ca 2+". convert_chem() rebuilds them as Unicode (H2O -> H₂O, [NO]² ...).

It is token-safe: a digit is only turned into a subscript when the token before it parses as a
chemical formula (real element symbols). English words and numbers ("Class 12", "In 2 hours",
"pH 7", "No 3") are left untouched, so it can run on whole stems/options without touching maths.

    convert_chem(text)      -> text with Unicode sub/superscripts
    conc_to_latex(text)     -> "[R 0 ]" -> "[R_{0}]"   (use on MATH runs that contain concentrations)
"""
import re

SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
SUP = str.maketrans("0123456789+-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻")
SUBCH = "₀₁₂₃₄₅₆₇₈₉"
SUPCH = "⁰¹²³⁴⁵⁶⁷⁸⁹"

ELEMENTS = set(
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br "
    "Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er "
    "Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md "
    "No Lr".split()
)
# element symbols that are also ordinary English words
STOP = {"In", "As", "At", "No", "He", "Be", "Am", "Ho", "Re", "Pa", "Po", "Os", "I", "Es"}

SYM = re.compile(r"[A-Z][a-z]?")
STATE = re.compile(r"\((?:g|l|s|aq)\)$")


def is_formula(tok: str) -> bool:
    t = STATE.sub("", tok)
    t = re.sub(r"^\d+", "", t)                                   # leading coefficient: 2NO
    t = re.sub(r"[\d()" + SUBCH + SUPCH + "⁺⁻]", "", t)
    if not t or t in STOP:
        return False
    pos = 0
    while pos < len(t):
        m = SYM.match(t, pos)
        if not m or m.group(0) not in ELEMENTS:
            return False
        pos = m.end()
    return True


def _brackets(s):                         # [O 2 ] -> [O₂] ; [R 0 ] -> [R₀]
    def inner(m):
        t = re.sub(r"(?<=[A-Za-z)])\s+(\d+)", lambda d: d.group(1).translate(SUB), m.group(1).strip())
        return "[" + t + "]"
    return re.sub(r"\[([^\[\]]*)\]", inner, s)


def _exponents(s):                        # [NO] 2 -> [NO]²   ([A] 0 -> [A]₀, an initial concentration)
    def f(m):
        n = m.group(1)
        return "]" + (n.translate(SUB) if n == "0" else n.translate(SUP))
    return re.sub(r"\]\s*(\d+)(?=$|[\s,.;:)\]\[])", f, s)


_PAT = re.compile(
    r"(?<!\S)(?P<tok>\S+)(?P<sp>[ \t]+)(?P<n>\d{1,2})(?P<ch>[+\-−]?)(?=$|[\s,.;:)\]]|\()"
)


def _subscripts(s):
    def f(m):
        tok, n, ch = m.group("tok"), m.group("n"), m.group("ch")
        if STATE.search(tok) or not is_formula(tok):
            return m.group(0)
        if ch:                                                   # charge: Ca 2+, SO₄ 2-
            return tok + n.translate(SUP) + ch.translate(SUP)
        if re.search(f"[{SUBCH}]$", tok):                        # already has a subscript
            return m.group(0)
        return tok + n.translate(SUB)
    return _PAT.sub(f, s)


def _groups(s):                           # (SO₄ ) 3 -> (SO₄)₃
    s = re.sub(f"(?<=[{SUBCH}])\\s+\\)", ")", s)
    def f(m):
        return m.group(0) if not is_formula(m.group(1)) else f"({m.group(1)}){m.group(2).translate(SUB)}"
    return re.sub(r"\(([A-Za-z" + SUBCH + r"]+)\)[ \t]+(\d+)(?=$|[\s,.;:)\]]|\()", f, s)


_JOIN = re.compile(f"(?<!\\S)(\\S*[{SUBCH}])[ \\t]+(\\S+)")


def _join(s):                             # H₂ O -> H₂O ; Al₂ (SO₄)₃ -> Al₂(SO₄)₃
    def f(m):
        a, b = m.group(1), m.group(2)
        return a + b if is_formula(a) and is_formula(b) else m.group(0)
    for _ in range(3):
        s = _JOIN.sub(f, s)
    return s


def _tidy(s):
    s = re.sub(f"(?<=[{SUBCH}])[ \\t]+(?=\\((?:g|l|s|aq)\\))", "", s)       # O₂ (g) -> O₂(g)
    s = re.sub(f"(?<=[{SUBCH}{SUPCH}\\]\\)])[ \\t]+(?=[,;])", "", s)          # HgCl₂ , -> HgCl₂,
    s = re.sub(r"\][ \t]+\[", "][", s)                                       # [NO] [O₂] -> [NO][O₂]
    s = re.sub(f"(?<=[{SUPCH}])[ \\t]+(?=\\[)", "", s)                       # [NO]² [O₂] -> [NO]²[O₂]
    s = re.sub(r"(?<![A-Za-z])([kK])[ \t]+(?=\[)", r"\1", s)                 # k [A] -> k[A]
    return s


def convert_chem(s: str) -> str:
    s = _brackets(s)
    s = _exponents(s)
    for _ in range(3):
        s = _subscripts(s)
    s = _groups(s)
    s = _join(s)
    return _tidy(s)


def conc_to_latex(s: str) -> str:
    """For MATH runs only: '\\log [R 0 ]' -> '\\log [R_{0}]'."""
    return re.sub(r"\[\s*([A-Za-z]+)\s+(\d+)\s*\]", r"[\1_{\2}]", s)


def suspect_options(options: dict) -> list:
    """Options that are only digits separated by spaces ('1 2', '1 4') are almost always a stacked
    fraction whose bar was lost. Return their labels so the question goes to review_list.json."""
    return [k for k, v in options.items() if re.fullmatch(r"\d+(?:\s+\d+)+", v.strip())]
