from src.corrections import apply_corrections

def test_apply_corrections_by_id():
    parsed = [
        {"id": "10", "question": "Original Q10", "options": {"A": "A10"}},
        {"id": "20", "question": "Original Q20", "options": {"A": "A20", "B": "B20"}}
    ]
    corr = {
        "10": {"options": {"A": "Corrected A10", "B": "New B10"}, "parsed_ok": True}
    }
    res = apply_corrections(parsed, corr)
    assert res[0]["options"]["A"] == "Corrected A10"
    assert res[0]["options"]["B"] == "New B10"
    assert res[0]["parsed_ok"] is True
    assert res[1]["options"]["A"] == "A20"

def test_apply_corrections_by_match():
    parsed = [
        {"id": "30", "question": "Statement I: foo bar"},
        {"id": "40", "question": "Something else"}
    ]
    corr = {
        "match1": {"match": "Statement I:", "options": {"B": "Both are incorrect"}}
    }
    res = apply_corrections(parsed, corr)
    assert res[0]["options"]["B"] == "Both are incorrect"
    assert "options" not in res[1] or "B" not in res[1].get("options", {})
