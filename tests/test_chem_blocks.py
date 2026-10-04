"""Run:  python test_chem_blocks.py   (or: pytest test_chem_blocks.py)
Cases are taken from the chemistry JSON (ids 47-67) plus common formula shapes."""
from src.chem_convert import convert_chem, conc_to_latex, suspect_options
from src.block_parse import parse_block, strip_noise
from src.convert.math import convert_math

CHEM = [  # raw PDF text -> expected
 ("ZnSO 4", "ZnSO₄"), ("AlCl 3", "AlCl₃"), ("BaCl 2", "BaCl₂"), ("NaCl", "NaCl"),          # id 47
 ("51. For 2NO(g) + O 2 (g) → 2NO 2(g) , the following initial-rate data were obtained. Choose the rate\nequation.",
  "51. For 2NO(g) + O₂(g) → 2NO₂(g), the following initial-rate data were obtained. Choose the rate\nequation."),
 ("Rate = k[NO] 2",             "Rate = k[NO]²"),                                            # id 51
 ("Rate = k[NO] 2 [O 2 ] 2",    "Rate = k[NO]²[O₂]²"),
 ("Rate = k[NO] [O 2 ]",        "Rate = k[NO][O₂]"),
 ("Rate = k[NO] 2 [O 2 ]",      "Rate = k[NO]²[O₂]"),
 ("Rate = K [A][B] 2",          "Rate = K[A][B]²"),                                          # id 55
 ("Rate = K [A] 2 [B] 2",       "Rate = K[A]²[B]²"),
 ("Rate = K [A] 2 [B]",         "Rate = K[A]²[B]"),
 ("Rate = K [A] [B]",           "Rate = K[A][B]"),
 ("56. In a reaction Hg + Cl 2 → HgCl 2 , the rate of disappearance of Hg is equal to",
  "56. In a reaction Hg + Cl₂ → HgCl₂, the rate of disappearance of Hg is equal to"),
 ("Rate of disappearance of Cl 2", "Rate of disappearance of Cl₂"),
 ("[R 0 ]", "[R₀]"),                                                                         # id 54
 ("Rate = k[A] [B] is", "Rate = k[A][B] is"),                                                # id 67
 # common shapes in this syllabus
 ("Ca(OH) 2", "Ca(OH)₂"), ("Al 2 (SO 4 ) 3", "Al₂(SO₄)₃"), ("H 2 O", "H₂O"), ("Fe 2 O 3", "Fe₂O₃"),
 ("Ca 2+", "Ca²⁺"), ("SO 4 2-", "SO₄²⁻"), ("[A] 0", "[A]₀"),
 ("N 2 + 3H 2 ⇌ 2NH 3", "N₂ + 3H₂ ⇌ 2NH₃"), ("CO 2 + H 2 O → H 2 CO 3", "CO₂ + H₂O → H₂CO₃"),
]

UNCHANGED = [  # plain English with element-like words and numbers must NOT be touched
 "In 2 hours the rate falls", "Class 12 students", "No 3 is correct", "Statement I is correct",
 "pH 7", "The half-life is 15 minutes", "Both (a) and (b)", "Zero order reaction",
 "Statement I: A catalyst does not alter Gibb’s energy (ΔG) of a reaction.",
 "The half-life period of a first-order reaction is 15 minutes.", "1 2",
]

RAW55 = ("For: Boar d s\n(D) Rate = 𝐾 [A] [B]\n\n55. In a reaction A + B → products, rate is doubled when the "
         "concentration of B is doubled, and\nrate increases by a factor of 8 when the concentrations of both the "
         "reactants (A and B. are\ndoubled. The rate law for the reaction can be written as:\n"
         "(A) Rate = K [A][B] 2\n(B) Rate = K [A] 2 [B] 2\n(C) Rate = K [A] 2 [B]\n✉")


def test_chem():
    for raw, want in CHEM:
        assert convert_chem(raw) == want, f"\n got:  {convert_chem(raw)!r}\n want: {want!r}"


def test_unchanged():
    for t in UNCHANGED:
        assert convert_chem(t) == t, f"changed: {t!r} -> {convert_chem(t)!r}"


def test_idempotent():
    for raw, want in CHEM:
        assert convert_chem(want) == want, want


def test_conc_in_math():                                                                    # id 54 option D
    assert convert_math(conc_to_latex(r"\log [R 0 ]")) == r"\log [R_{0}]"


def test_suspect_fraction_options():                                                        # ids 59, 67
    assert suspect_options({"A": "0", "B": "1", "C": "1 2", "D": "2"}) == ["C"]
    assert suspect_options({"A": "1", "B": "2", "C": "1 2", "D": "1 4"}) == ["C", "D"]
    assert suspect_options({"A": "One", "B": "Two", "C": "Zero", "D": "Three"}) == []


def test_q55_orphan_D_header_and_glyphs():                                                  # id 55
    r = parse_block(RAW55)
    assert r["stem"].startswith("55. In a reaction A + B → products")
    assert r["stem"].endswith("can be written as:")
    assert r["options"] == {"A": "Rate = K [A][B] 2", "B": "Rate = K [A] 2 [B] 2",
                            "C": "Rate = K [A] 2 [B]", "D": "Rate = K [A] [B]"}      # 𝐾 -> K, orphan D attached
    assert "✉" not in r["stem"] and "Boar" not in r["stem"] and r["spill"] == {}


def test_q48_q62_header_and_chapter():                                                      # ids 48, 62
    r = parse_block("For: Boar d s\nChemical Kinetics:\n48. Which of these statements about a galvanic cell are "
                    "not true?\ni) The cathode carries a positive sign.\nii) Oxidation occurs at the anode.")
    assert r["chapter"] == "Chemical Kinetics" and r["stem"].startswith("48. Which")
    assert "ii) Oxidation occurs at the anode." in r["stem"]          # i) ii) are stem lines, not options
    assert parse_block("For: Boar d s\n62. The collision frequency in a reaction depends on")["stem"] == \
           "62. The collision frequency in a reaction depends on"
    assert parse_block("3+ For: Boar d s\n44. The product formed at the anode during the electrolysis of aqueous NaCl is")["stem"] == \
           "44. The product formed at the anode during the electrolysis of aqueous NaCl is"


def test_stem_line_ending_in_colon_is_kept():
    r = parse_block("12. Identify the correct statement:\nA. one\nB. two\nwrapped two\nC. three\nD. four")
    assert r["stem"] == "12. Identify the correct statement:" and r["chapter"] is None
    assert r["options"]["B"] == "two wrapped two"


def test_orphan_that_belongs_to_previous_question():
    r = parse_block("(D) leftover\n\n9. New question\nA. a\nB. b\nC. c\nD. d")
    assert r["spill"] == {"D": "leftover"} and r["options"]["D"] == "d"


if __name__ == "__main__":
    for f in (test_chem, test_unchanged, test_idempotent, test_conc_in_math, test_suspect_fraction_options,
              test_q55_orphan_D_header_and_glyphs, test_q48_q62_header_and_chapter,
              test_stem_line_ending_in_colon_is_kept, test_orphan_that_belongs_to_previous_question):
        f(); print("ok ", f.__name__)
