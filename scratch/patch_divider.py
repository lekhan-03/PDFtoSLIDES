import re

def patch_file(filepath, search, replace):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    if search in text:
        text = text.replace(search, replace)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Patched {filepath}")
    else:
        print(f"Could not find search string in {filepath}")

# patch parser.py
search_parser = """    if not question or any(not v for v in options.values()):
        result["parsed_ok"] = False
        return result"""

replace_parser = """    if not options:
        words = question.split()
        if len(words) <= 4 and question and question[0].isalpha():
            result["question_type"] = "divider"
            result["id"] = None
            result["parsed_ok"] = True
            return result

    if not question or any(not v for v in options.values()):
        result["parsed_ok"] = False
        return result"""
patch_file("src/parser.py", search_parser, replace_parser)

# patch extract_pdf.py
search_pdf = """    else:
        result["question"] = text.strip()
        result["question_type"] = "open"
        result["parsed_ok"] = True"""

replace_pdf = """    else:
        question_text = text.strip()
        words = question_text.split()
        if len(words) <= 4 and question_text and question_text[0].isalpha():
            result["question"] = question_text
            result["question_type"] = "divider"
            result["id"] = None
            result["parsed_ok"] = True
        else:
            result["question"] = question_text
            result["question_type"] = "open"
            result["parsed_ok"] = True"""
patch_file("src/extract_pdf.py", search_pdf, replace_pdf)
