import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parser import split_questions, parse_block, parse_all


def test_normal_question():
    lines = [
        "1. What is the capital of France?",
        "(A) Berlin",
        "(B) Madrid",
        "(C) Paris",
        "(D) Rome",
        "2. Next question stem",
        "(A) 1", "(B) 2", "(C) 3", "(D) 4",
    ]
    blocks = split_questions(lines)
    assert len(blocks) == 2
    r = parse_block(blocks[0])
    assert r["parsed_ok"]
    assert r["question"] == "What is the capital of France?"
    assert r["options"] == {"A": "Berlin", "B": "Madrid", "C": "Paris", "D": "Rome"}


def test_inline_options_same_line():
    lines = ["1. Pick one (A) 1 (B) 2 (C) 3 (D) 4"]
    r = parse_block(split_questions(lines)[0])
    assert r["parsed_ok"]
    assert r["options"]["C"] == "3"


def test_number_inside_question_does_not_split():
    lines = [
        "1. Concentration more than 0.9% is used here",
        "(A) one", "(B) two", "(C) three", "(D) four",
    ]
    blocks = split_questions(lines)
    assert len(blocks) == 1
    assert blocks[0]["id"] == 1


def test_match_the_column_parsed_correctly():
    # Column II labels (A)-(D) appear before the real answer options.
    # The parser must detect the REAL options (content starts with pairing
    # like "(1)-(A)") and parse them correctly, not flag as failed.
    lines = [
        "1. Match items: (1) X (A) foo (2) Y (B) bar "
        "(A) (1)-(A) (B) (1)-(B) (C) (1)-(C) (D) (1)-(D)"
    ]
    r = parse_block(split_questions(lines)[0])
    assert r["parsed_ok"], f"Expected match-the-column to parse OK, got: {r}"
    assert r.get("question_type") == "match_the_column"
    # The real options are the pairing strings, NOT the column labels
    assert "(1)-(A)" in r["options"]["A"]
    assert "(1)-(B)" in r["options"]["B"]
    assert "(1)-(C)" in r["options"]["C"]
    assert "(1)-(D)" in r["options"]["D"]


def test_double_lettering_without_pairing_flagged():
    # A block where option D contains another (D) but there is NO pairing
    # pattern -- parser cannot rescue it, must stay parsed_ok=False.
    lines = ["1. Pick: (A) alpha (B) beta (C) gamma (D) delta (D) again"]
    r = parse_block(split_questions(lines)[0])
    assert not r["parsed_ok"]


def test_missing_option_flagged():
    lines = ["1. Incomplete question", "(A) only one option here"]
    r = parse_block(split_questions(lines)[0])
    assert not r["parsed_ok"]


def test_parse_all_separates_failed():
    lines = [
        "1. Good one", "(A) a", "(B) b", "(C) c", "(D) d",
        "2. Bad one", "(A) only",
    ]
    parsed, failed = parse_all(lines)
    assert len(parsed) == 1
    assert len(failed) == 1
    assert failed[0]["id"] == 2
