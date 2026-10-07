"""Run:  python test_math_convert.py   (or: pytest test_math_convert.py)
Expected values were checked by hand against the source PDF text patterns in Integrals.json."""
from src.convert.math import convert_math, check_math, split_question

# (id in Integrals.json, raw MATH run as extracted, expected LaTeX)
CONVERT = [
 ("128a", r"∫_{a}^{b} f(x).dx=∫_{a}^{b} f(a+b-x)dx",
          r"\int_{a}^{b} f(x)\,dx=\int_{a}^{b} f(a+b-x)\,dx"),
 ("128b", r"∫_{(π)/(6)}^{(π)/(3)} (1)/(1+sqrt(tanx)) dx",
          r"\int_{\frac{\pi}{6}}^{\frac{\pi}{3}} \frac{1}{1+\sqrt{\tan x}}\,dx"),
 # piecewise: three real variants (comma / no comma, "f (x)is", "is an even function")
 ("129a", r"∫_{0}^{a} f(x).dx={2∫_{0}^{a} f(x)dx, if f(2a-x)=f(x) 0, if f(2a-x)= -f(x) ",
          r"\int_{0}^{a} f(x)\,dx = \begin{cases} 2\int_{0}^{a} f(x)\,dx & \text{if } f(2a-x)=f(x) \\ 0 & \text{if } f(2a-x)=-f(x) \end{cases}"),
 ("133a", r"∫_{-a}^{a} f(x)dx={2∫_{0}^{a} f(x)dx if f(x) is even function 0,if f (x)is odd function ",
          r"\int_{-a}^{a} f(x)\,dx = \begin{cases} 2\int_{0}^{a} f(x)\,dx & \text{if } f(x)\text{ is even function} \\ 0 & \text{if } f(x)\text{ is odd function} \end{cases}"),
 ("135a", r"∫_{-a}^{a} f(x).dx= {2∫_{0}^{a} f(x)dx, if f(x)is an even function 0, if f(x)is an odd function ",
          r"\int_{-a}^{a} f(x)\,dx = \begin{cases} 2\int_{0}^{a} f(x)\,dx & \text{if } f(x)\text{ is an even function} \\ 0 & \text{if } f(x)\text{ is an odd function} \end{cases}"),
 ("129b", r"∫_{0}^{2π} cos^{5}x dx",            r"\int_{0}^{2\pi} \cos^{5}x\,dx"),
 ("131",  r"∫_{0}^{(π)/(2)} (2loglog sinx-loglog sin2x) dx",
          r"\int_{0}^{\frac{\pi}{2}} (2\log \sin x-\log \sin 2x)\,dx"),
 ("133b", r"∫_{-(π)/(2)}^{(π)/(2)} sin7x dx",    r"\int_{-\frac{\pi}{2}}^{\frac{\pi}{2}} \sin 7x\,dx"),
 ("134",  r"∫_{0}^{(π)/(2)} (cos^{5}x)/(cos^{5}x+sin^{5}x) dx",
          r"\int_{0}^{\frac{\pi}{2}} \frac{\cos^{5}x}{\cos^{5}x+\sin^{5}x}\,dx"),
 ("135b", r"∫_{-1}^{1} sin^{5}xcos^{4}x dx ",   r"\int_{-1}^{1} \sin^{5}x\cos^{4}x\,dx"),
 ("136a", r"∫_{0}^{a} f(x).dx=∫_{a}^{c} f(x)dx+∫_{c}^{b} f(x)dx",
          r"\int_{0}^{a} f(x)\,dx=\int_{a}^{c} f(x)\,dx+\int_{c}^{b} f(x)\,dx"),
 # earlier slides
 ("cosec", "\\cosec\u2061^{-1}x+C",              r"\csc^{-1}x+C"),
 ("xcos",  "-xcosx-sinx+c",                      r"-x\cos x-\sin x+c"),
]

# Formulas that convert fine but are WRONG at the source. check_math must flag them.
MUST_FLAG = [
 ("130b", r"∫_{0}^{(π)/(2)} (sqrt(sinx))/(sqrt(sinx)sqrt(cosx))", "differential"),   # no dx (and the + is missing)
 ("132b", r"∫_{0}^{a} (sqrt(x))/(sqrt(x)+sqrt(a-x))",              "differential"),   # no dx
 ("136b", r"∫_{-1}^{2} dx ",                                       "empty integrand"),
]

SPLIT = [
 # bare "dx" outside the $ pair is re-attached, tag pulled out, space-padded $ trimmed
 (r"Prove that$∫_{-a}^{a} f(x)dx=1 $ and hence evaluate $∫_{0}^{(π)/(2)} (cos^{5}x)/(cos^{5}x+sin^{5}x)$ dx (2019,2023,2024-2)",
  "2019,2023,2024-2",
  [("TEXT", "Prove that"), ("MATH", "∫_{-a}^{a} f(x)dx=1"), ("TEXT", " and hence evaluate "),
   ("MATH", "∫_{0}^{(π)/(2)} (cos^{5}x)/(cos^{5}x+sin^{5}x) dx")]),
 (r"Prove that $∫_{0}^{a} f(x).dx=∫_{0}^{a} f(a-x)dx$ and hence evaluate$∫_{0}^{a} f(x)dx$ (2016s,2022,2026-1)",
  "2016s,2022,2026-1",
  [("TEXT", "Prove that "), ("MATH", "∫_{0}^{a} f(x).dx=∫_{0}^{a} f(a-x)dx"), ("TEXT", " and hence evaluate"),
   ("MATH", "∫_{0}^{a} f(x)dx")]),
 ("Prove that no math here (2017)", "2017", [("TEXT", "Prove that no math here")]),
 (r"$∫ (2-3 sinx)/(cos^{2}x)$ dx = (2026M)", "2026M",
  [("MATH", r"∫ (2-3 sinx)/(cos^{2}x) dx"), ("TEXT", " =")]),
]


def test_convert():
    for id_, raw, want in CONVERT:
        got = convert_math(raw)
        assert got == want, f"{id_}\n got:  {got}\n want: {want}"
        assert check_math(got) == [], f"{id_} flagged: {check_math(got)}"


def test_must_flag():
    for id_, raw, needle in MUST_FLAG:
        probs = check_math(convert_math(raw))
        assert any(needle in p for p in probs), f"{id_} should be flagged ({needle}), got {probs}"


def test_split():
    for q, tag, runs in SPLIT:
        t, r = split_question(q)
        assert (t, r) == (tag, runs), f"\n got:  {(t, r)}\n want: {(tag, runs)}"


def test_idempotent():          # converting twice must not change anything
    for id_, raw, want in CONVERT:
        assert convert_math(want) == want, id_


if __name__ == "__main__":
    for f in (test_convert, test_must_flag, test_split, test_idempotent):
        f(); print("ok ", f.__name__)
