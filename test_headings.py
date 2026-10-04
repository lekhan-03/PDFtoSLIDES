from headings import is_heading, strip_trailing_heading


def test_is_heading():
    for t in ["Solutions", "Chemical Kinetics", "Electrochemistry", "MCQ’s"]:
        assert is_heading(t), t
    for t in ["Integrate $∫ (2-3sinx)/(cos^{2}x)$ (2023)", "Evaluate $∫_{1}^{sqrt(3)} 3$ (2023,2024-1)",
              "Evaluate ∫ x dx", "[IMG: a/b.png]", "Which of these is true?"]:
        assert not is_heading(t), t


def test_trailing_heading_is_cut_from_the_last_option():          # chemistry Q44, option D
    assert strip_trailing_heading("Cl 2 Application Based Questions:") == ("Cl 2", "Application Based Questions")
    assert strip_trailing_heading("Cl₂ Electrochemistry:") == ("Cl₂", "Electrochemistry")


def test_normal_options_are_untouched():
    for t in ["Cl 2", "Both statements are true:", "Strongest reducing agent", "SEP value is zero",
              "Rate = k[NO]²", "the pressure is high and temperature is low."]:
        assert strip_trailing_heading(t) == (t, None), t


if __name__ == "__main__":
    for f in (test_is_heading, test_trailing_heading_is_cut_from_the_last_option, test_normal_options_are_untouched):
        f(); print("ok ", f.__name__)
