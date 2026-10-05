from src.headings import is_heading

def test_is_heading():
    assert is_heading("Solutions") == True
    assert is_heading("Application Based Questions:") == True
    assert is_heading("Electrochemistry:") == True
    assert is_heading("d and F Block elements:") == True
    assert is_heading("This is a long sentence that is not a heading") == False
    assert is_heading("(A) This is an option") == False
    assert is_heading("1. A question") == False
    assert is_heading("osmosis") == False # single word, lowercase
    assert is_heading("and the cell shrinks.") == False # lowercase
