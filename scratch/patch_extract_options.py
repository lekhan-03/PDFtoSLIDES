import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

old_logic = """        if '\\n' in opt_text:
            opt_text = opt_text.split('\\n')[0].strip()"""
new_logic = """        if '\\n' in opt_text:
            opt_text = " ".join(line.strip() for line in opt_text.split('\\n') if line.strip())"""

text = text.replace(old_logic, new_logic)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
