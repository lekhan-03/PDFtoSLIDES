import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

old_check = """        # Split by newlines from the end to find a heading
        lines = opt_text.split('\\n')
        for i in range(len(lines)):
            suffix = '\\n'.join(lines[i:]).strip()
            if is_heading(suffix) and '\\n'.join(lines[:i]).strip():
                result["options"][last_opt] = '\\n'.join(lines[:i]).strip()
                divider = {
                    "question_type": "divider",
                    "question": suffix,
                    "id": None,
                    "parsed_ok": True
                }
                return [result, divider]"""

new_check = """        words = opt_text.split()
        for i in range(1, len(words)):
            suffix = ' '.join(words[-i:]).strip()
            if is_heading(suffix) and ' '.join(words[:-i]).strip():
                result["options"][last_opt] = ' '.join(words[:-i]).strip()
                divider = {
                    "question_type": "divider",
                    "question": suffix,
                    "id": None,
                    "parsed_ok": True
                }
                return [result, divider]"""

text = text.replace(old_check, new_check)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
