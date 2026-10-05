with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

old_loop = """        if is_heading(suffix) and ' '.join(words[:-i]).strip():
            result["options"][last_opt] = ' '.join(words[:-i]).strip()"""
new_loop = """        if is_heading(suffix) and ' '.join(words[:-i]).strip():
            print(f"DEBUG: suffix={suffix}, prefix={' '.join(words[:-i])}")
            result["options"][last_opt] = ' '.join(words[:-i]).strip()"""

text = text.replace(old_loop, new_loop)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
