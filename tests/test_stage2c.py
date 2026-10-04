"""Run: python test_stage2c.py (or pytest). New cases only - the earlier test files stay untouched."""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_merge import merge_runs
from src.chem_extra import attached_subscripts
from src.chem_convert import convert_chem
from src.convert.math import split_question, convert_math, check_math

RAW6 = ('Statement 1: The anti-derivative of $((1)/(sqrt(1+X^{2})) )$with respect to x is $(X)/(2)$ $sqrt(1+X^{2})$ '
        '+$(1)/(2)$ log|𝑥 +$sqrt(1+X^{2})$| + 𝐶\nStatement 2: The derivative of $ (X)/(2)$ $sqrt(1+X^{2})$ '
        '+$(1)/(2)$ log|𝑥 +$sqrt(1+X^{2})$| + 𝐶. with respect to x is $(1)/(sqrt(1+X^{2}))$ (2025M)')
GLUED = "(X)/(2) sqrt(1+X^{2}) + (1)/(2) log|x + sqrt(1+X^{2}) | + C"


def test_id6_is_one_expression_per_statement():
    tag, runs = split_question(RAW6)
    got = merge_runs(runs)
    assert tag == "2025M"
    assert got == [
        ("TEXT", "Statement 1: The anti-derivative of "), ("MATH", "((1)/(sqrt(1+X^{2})) )"),
        ("TEXT", "with respect to x is "), ("MATH", GLUED),
        ("TEXT", "\nStatement 2: The derivative of "), ("MATH", GLUED),
        ("TEXT", ". with respect to x is "), ("MATH", "(1)/(sqrt(1+X^{2}))")], got
    latex = convert_math(GLUED)
    assert latex == r"\frac{X}{2} \sqrt{1+X^{2}} + \frac{1}{2} \log |x + \sqrt{1+X^{2}} | + C"
    assert check_math(latex) == []


def test_no_math_italic_letters_survive():
    for k, t in merge_runs(split_question(RAW6)[1]):
        assert not any(0x1D400 <= ord(c) <= 0x1D7FF for c in t), (k, t)


def test_trailing_equals_joins_the_integral():                       # id 9
    assert merge_runs([("MATH", "∫ (2-3 sinx)/(cos^{2}x) dx"), ("TEXT", " =")]) == \
           [("MATH", "∫ (2-3 sinx)/(cos^{2}x) dx =")]


def test_english_and_labels_are_never_glued():
    same = [
        [("TEXT", "Find "), ("MATH", "x"), ("TEXT", " and "), ("MATH", "y"), ("TEXT", " if ")],
        [("TEXT", "Let "), ("MATH", "a"), ("TEXT", ", "), ("MATH", "b")],         # comma only
        [("MATH", "x"), ("TEXT", " (a) is true")],                                  # option label
        [("MATH", "x"), ("TEXT", " with respect to x is ")],
    ]
    for runs in same:
        assert merge_runs(runs) == runs, runs


def test_leading_math_before_a_formula_joins():
    assert merge_runs([("TEXT", "Evaluate 2 + "), ("MATH", "x")]) == [("TEXT", "Evaluate "), ("MATH", "2 + x")]
    assert merge_runs([("MATH", "x"), ("TEXT", " "), ("MATH", "y")]) == [("MATH", "x y")]
    assert merge_runs([("MATH", "∫ f(x)dx"), ("TEXT", " + c")]) == [("MATH", "∫ f(x)dx + c")]   # option text


ATTACHED = [("(CCl4)", "(CCl₄)"), ("CH2Cl2", "CH₂Cl₂"), ("(1) Carbon tetrachloride (CCl4)", "(1) Carbon tetrachloride (CCl₄)"),
            ("H2O", "H₂O"), ("2NO2(g)", "2NO₂(g)"), ("C2H5OH,", "C₂H₅OH,"), ("H2SO4", "H₂SO₄"),
            ("Na2CO3(aq)", "Na₂CO₃(aq)"), ("[N2O5]", "[N₂O₅]"), ("Ca(OH)2", "Ca(OH)₂"), ("KMnO4", "KMnO₄")]
KEEP = ["pH7", "NEET2025", "JEE2024", "Q5", "2023M", "A4", "Statement1", "Class12", "Section2", "COVID19",
        "CBSE2025", "UPSC2020", "KVPY2020", "SSLC10", "Option2", "No1", "In2", "Both (a) and (b)", "15 minutes"]


def test_attached_subscripts():
    for raw, want in ATTACHED:
        assert attached_subscripts(raw) == want, (raw, attached_subscripts(raw))


def test_attached_leaves_non_formulas_alone():
    for t in KEEP:
        assert attached_subscripts(t) == t, t


def test_attached_and_spaced_forms_agree():
    for a, b in [("H2O", "H 2 O"), ("CO2", "CO 2"), ("Ca(OH)2", "Ca(OH) 2")]:
        assert convert_chem(attached_subscripts(a)) == convert_chem(attached_subscripts(b))


if __name__ == "__main__":
    for f in (test_id6_is_one_expression_per_statement, test_no_math_italic_letters_survive,
              test_trailing_equals_joins_the_integral, test_english_and_labels_are_never_glued,
              test_leading_math_before_a_formula_joins, test_attached_subscripts,
              test_attached_leaves_non_formulas_alone, test_attached_and_spaced_forms_agree):
        f(); print("ok ", f.__name__)
