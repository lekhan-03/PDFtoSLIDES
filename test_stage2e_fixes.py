"""New cases from the Stage 2e report (real strings). Run: python test_stage2e_fixes.py"""
from unmarked import split_unmarked, option_tag_report, suspect_swallowed, is_english
from math_convert import convert_math, check_math


def test_sqrt_is_math_not_english():                    # Integrals "∫_{1}^{sqrt(3)} 3" was classified TEXT
    assert not is_english("sqrt") and not is_english("xsqrt")
    runs = split_unmarked("∫_{1}^{sqrt(3)} 3 ")
    assert runs == [("MATH", "∫_{1}^{sqrt(3)} 3")], runs
    latex = convert_math(runs[0][1])
    assert latex == r"\int_{1}^{\sqrt{3}} 3" and check_math(latex) == ["1 integral sign(s) but 0 differential(s)"]


def test_unicode_superscript_and_dash_options():       # ids 18, 19, 22
    want = {"sec² x + tan x + c": r"\sec^{2} x + \tan x + c",
            "−eˣ cos x + c": r"−e^{x} \cos x + c",
            "x – sec2x + c": r"x - \sec 2x + c"}
    for raw, latex in want.items():
        assert split_unmarked(raw) == [("MATH", raw)], raw
        assert convert_math(raw) == latex, (raw, convert_math(raw))


def test_invisible_function_application_sign():
    assert split_unmarked("sec\u2061x+C") == [("MATH", "secx+C")]


REAL = {  # (stem tag, options) copied from the report
 "Integrals 4":  (None, {"A": "0", "B": "point of inflection does not exist", "C": "$-(π)/(2)$",
                         "D": "$(π)/(2)$ $∫(1)/(xsqrt(x^{2}-1)) dx=$ (2025M)"}),
 "Integrals 8":  (None, {"D": "$cot⁡^{-1}x+C$ $∫ (2-3 sinx)/(cos^{2}x)$ dx = (2026M)"}),
 "Integrals 22": (None, {"D": "x – sec2x + c $∫e^{x}(sin⁡x-cos⁡x) dx$ is (2025-1)"}),
 "Chemistry 8":  (None, {"D": "the pressure is high and temperature is low. Which of the following conditions is "
                              "favourable for the production of ammonia by Haber's process? (2018s)"}),
}
OWN_TAG = {   # the tag after option D is the question's own tag - NOT a swallowed question
 "Integrals 16": ("2026M", {"D": "$(3)/(2)x^{3/2}+(1)/(2)x^{1/2}+c$ (2026M)"}),
 "Integrals 17": ("2026M", {"D": "$tan⁡2x+c$ (2026M)"}),
 "Integrals 18": ("2024-1", {"D": "−eˣ cos x + c (2024-1)"}),
 "Integrals 19": ("2024-1", {"D": "- tan x - sec x + c (2024-1)"}),
 "Integrals 20": ("2024-2", {"D": "cot x − cosec x + c (2024-2)"}),
}


def test_real_swallows_are_flagged():
    for name, (tag, opts) in REAL.items():
        t, cleaned, swallowed = option_tag_report(tag, opts)
        assert swallowed == ["D"], name
        assert cleaned["D"] == opts["D"], name            # untouched, goes to review_list
        assert suspect_swallowed(opts) == ["D"], name


def test_own_tag_after_last_option_moves_to_question():  # was a false positive in the report
    for name, (want_tag, opts) in OWN_TAG.items():
        t, cleaned, swallowed = option_tag_report(None, opts)
        assert swallowed == [] and t == want_tag, (name, t, swallowed)
        assert "(" + want_tag + ")" not in cleaned["D"], name
    # stem already has the tag: nothing changes for the question tag
    assert option_tag_report("2024-1", {"D": "x + c (2024-1)"})[0] == "2024-1"


if __name__ == "__main__":
    for f in (test_sqrt_is_math_not_english, test_unicode_superscript_and_dash_options,
              test_invisible_function_application_sign, test_real_swallows_are_flagged,
              test_own_tag_after_last_option_moves_to_question):
        f(); print("ok ", f.__name__)
