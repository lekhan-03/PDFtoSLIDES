"""Run: python test_unmarked.py (or pytest). Cases come from your three screenshots plus guards."""
from src.unmarked import is_english, looks_like_math, split_unmarked, split_runs_auto, suspect_swallowed
from src.convert.math import convert_math, check_math

ENGLISH = ["second", "since", "Since", "consider", "tangent", "secant", "cosecant", "cosine", "logarithm",
           "single", "sector", "the", "find", "value"]
MATHWORDS = ["secx", "sinx", "xcosx", "cosecx", "lnx", "logx", "tanxsecx", "dx", "cos", "sin"]


def test_is_english():                                  # regression: v1 treated second/since/tangent as math
    for w in ENGLISH:
        assert is_english(w), w
    for w in MATHWORDS:
        assert not is_english(w), w


def test_image1_stem_has_text_and_math_separated():     # "Findthevalueof" glued into one italic equation
    tag, runs = split_runs_auto("Find the value of ∫_{-1}^{1} x^{99} dx = (2026M)")
    assert tag == "2026M"
    assert runs == [("TEXT", "Find the value of "), ("MATH", "∫_{-1}^{1} x^{99} dx =")], runs
    assert convert_math(runs[1][1]) == r"\int_{-1}^{1} x^{99}\,dx ="


def test_image2_options():                              # "-(π)/(2)" printed as raw text
    assert split_unmarked("-(π)/(2)") == [("MATH", "-(π)/(2)")]
    assert convert_math("-(π)/(2)") == r"-\frac{\pi}{2}"
    assert split_unmarked("(π)/(2)") == [("MATH", "(π)/(2)")]
    assert split_unmarked("point of inflection does not exist") == [("TEXT", "point of inflection does not exist")]
    assert split_unmarked("The point of inflection for the following graph is") == \
           [("TEXT", "The point of inflection for the following graph is")]
    assert split_unmarked("0") == [("TEXT", "0")] and split_unmarked("1") == [("TEXT", "1")]


def test_image3_options_are_all_math():                 # secx+C plain, \cosec^{-1}x+C raw backslash, sec^{-1} math
    want = {"secx+C": r"\sec x+C", "cosecx+C": r"\csc x+C",
            "\\cosec^{-1}x+C": r"\csc^{-1}x+C", "sec^{-1}x+C": r"\sec^{-1}x+C"}
    for raw, latex in want.items():
        assert split_unmarked(raw) == [("MATH", raw)], raw
        assert convert_math(raw) == latex and check_math(latex) == [], raw


def test_english_with_function_names_stays_text():
    for s in ["The second derivative of the curve", "Since the function is even", "The tangent to the curve",
              "Find the secant line", "Consider the cosecant of the angle"]:
        assert split_unmarked(s) == [("TEXT", s)], s


def test_math_inside_a_sentence():
    assert split_unmarked("The tangent to the curve y = x^{2} at the origin") == \
           [("TEXT", "The tangent to the curve "), ("MATH", "y = x^{2}"), ("TEXT", " at the origin")]
    assert split_unmarked("47. Evaluate ∫ sinx dx.") == \
           [("TEXT", "47. Evaluate "), ("MATH", "∫ sinx dx"), ("TEXT", ".")]


def test_chemistry_is_never_taken_for_math():
    for s in ["Rate = K[A][B] 2", "Rate = k[NO] 2 [O 2 ]", "[R 0 ]", "Both (a) and (b)", "Zero order reaction",
              "NO2 + O2", "CO2 + H2O", "2NO(g) + O 2 (g) → 2NO 2(g)", "i and iii",
              "For 2NO(g) + O 2 (g) → 2NO 2(g) , the following initial-rate data were obtained.",
              "56. In a reaction Hg + Cl 2 → HgCl 2 , the rate of disappearance of Hg is equal to"]:
        assert split_unmarked(s) == [("TEXT", s)], (s, split_unmarked(s))
    assert not looks_like_math("NO2 + O2")


def test_option_that_swallowed_the_next_question():     # image 2, option D
    opts = {"A": "0", "B": "point of inflection does not exist", "C": "-(π)/(2)",
            "D": "(π)/(2)∫ (1)/(xsqrt(x^{2}-1))dx = (2025M)"}
    assert suspect_swallowed(opts) == ["D"]
    assert suspect_swallowed({"A": "0", "B": "1"}) == []


if __name__ == "__main__":
    for f in (test_is_english, test_image1_stem_has_text_and_math_separated, test_image2_options,
              test_image3_options_are_all_math, test_english_with_function_names_stays_text,
              test_math_inside_a_sentence, test_chemistry_is_never_taken_for_math,
              test_option_that_swallowed_the_next_question):
        f(); print("ok ", f.__name__)
