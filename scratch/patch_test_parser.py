import re
with open("tests/test_parser.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("def test_extract_options_multiline_and_noise")
if idx != -1:
    text = text[:idx]

new_test = """def test_extract_options_multiline_and_noise():
    # Q52 text with newlines
    q52_text = \"\"\"1. q
(A) Rate constant increases exponentially with increasing activation energy and decreasing
temperature.
(B) Rate constant decreases exponentially with increasing activation energy and decreasing
temperature.
(C) Rate constant increases exponentially with increasing activation energy and increasing
temperature.
(D) Rate constant increases exponentially with decreasing activation energy and decreasing
temperature.\"\"\"
    from src.parser import parse_block
    r = parse_block({"lines": q52_text.split('\\n'), "id": 1, "section": "MCQ"})
    for k in "ABCD":
        assert r["options"][k].endswith("temperature.")
        
    # Q55 style text with noise
    q55_text = \"\"\"2. q
(A) a (B) b (C) c (D) d
For: Boar d s
watermark text
✉\"\"\"
    r2 = parse_block({"lines": q55_text.split('\\n'), "id": 2, "section": "MCQ"})
    assert r2["options"]["D"] == "d"
    assert "✉" not in r2["options"]["D"]
    assert "For: Boar d s" not in r2["options"]["D"]
    assert "watermark text" not in r2["options"]["D"]
"""
text += new_test
with open("tests/test_parser.py", "w", encoding="utf-8") as f:
    f.write(text)
