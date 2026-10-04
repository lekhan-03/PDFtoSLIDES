import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

old_divider = """        words = text.strip().split()
        if len(words) <= 4 and text.strip() and text.strip()[0].isalpha():"""

new_divider = """        words = text.strip().split()
        if len(words) <= 4 and text.strip() and text.strip()[0].isalpha() and not re.search(r'\\([A-Da-d]\\)', text):"""

text = text.replace(old_divider, new_divider)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("src/extract_pdf.py", "r", encoding="utf-8") as f:
    text2 = f.read()

old_divider_pdf = """        words = question_text.split()
        if len(words) <= 4 and question_text and question_text[0].isalpha():"""

new_divider_pdf = """        words = question_text.split()
        import re
        if len(words) <= 4 and question_text and question_text[0].isalpha() and not re.search(r'\\([A-Da-d]\\)', question_text):"""

text2 = text2.replace(old_divider_pdf, new_divider_pdf)

with open("src/extract_pdf.py", "w", encoding="utf-8") as f:
    f.write(text2)
