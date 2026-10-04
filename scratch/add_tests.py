
def test_extract_options_multiline_and_noise():
    # Q52 text with newlines
    q52_text = """(A) Rate constant increases exponentially with increasing activation energy and decreasing
temperature.
(B) Rate constant decreases exponentially with increasing activation energy and decreasing
temperature.
(C) Rate constant increases exponentially with increasing activation energy and increasing
temperature.
(D) Rate constant increases exponentially with decreasing activation energy and decreasing
temperature."""
    from src.parser import _extract_options, _find_options
    pos = _find_options(q52_text)
    options = _extract_options(q52_text, pos)
    for k in "ABCD":
        assert options[k].endswith("temperature.")
        
    # Q55 style text with noise
    q55_text = """(A) a (B) b (C) c (D) d
For: Boar d s
watermark text
✉"""
    pos2 = _find_options(q55_text)
    options2 = _extract_options(q55_text, pos2)
    assert options2["D"] == "d"
    assert "✉" not in options2["D"]
    assert "For: Boar d s" not in options2["D"]
    assert "watermark text" not in options2["D"]
