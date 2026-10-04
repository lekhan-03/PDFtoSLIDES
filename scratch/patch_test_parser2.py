import re

with open("tests/test_parser.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add the new test
new_test = """
def test_inline_options_with_noise():
    from src.parser import parse_block
    # Test 1
    block1 = {
        "id": 1,
        "section": "Chemistry",
        "lines": [
            "Which of the following is correct?",
            "(A) ppm (B) mole fraction (C) molality (D) molarity",
            "For: Boar d s",
            "✉ learn@simplifiedminds.com"
        ]
    }
    res1 = parse_block(block1)
    assert res1["parsed_ok"]
    assert res1["options"]["A"] == "ppm"
    assert res1["options"]["B"] == "mole fraction"
    assert res1["options"]["C"] == "molality"
    assert res1["options"]["D"] == "molarity"

    # Test 2
    block2 = {
        "id": 2,
        "section": "Chemistry",
        "lines": [
            "Which is an example of solid solution?",
            "(A) Hydrogen in palladium (B) Camphor in nitrogen gas (C) Amalgam of mercury & sodium (D) Copper in gold"
        ]
    }
    res2 = parse_block(block2)
    assert res2["parsed_ok"]
    assert res2["options"]["A"] == "Hydrogen in palladium"
    assert res2["options"]["B"] == "Camphor in nitrogen gas"
    assert res2["options"]["C"] == "Amalgam of mercury & sodium"
    assert res2["options"]["D"] == "Copper in gold"
"""

if "def test_inline_options_with_noise" not in text:
    with open("tests/test_parser.py", "a", encoding="utf-8") as f:
        f.write("\n" + new_test)
