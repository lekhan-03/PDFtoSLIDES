with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text = f.read()

text = "from src.headings import is_heading\n" + text

old_divider = """        words = question_text.split()
        import re
        if len(words) <= 4 and question_text and question_text[0].isalpha() and not re.search(r'\\([A-Da-d]\\)', question_text):"""
new_divider = """        if is_heading(question_text):"""

text = text.replace(old_divider, new_divider)

with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text)
