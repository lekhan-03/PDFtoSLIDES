import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add import
text = "from src.headings import is_heading\n" + text

# Use is_heading for dividers
old_divider = """        words = text.strip().split()
        if len(words) <= 4 and text.strip() and text.strip()[0].isalpha() and not re.search(r'\\([A-Da-d]\\)', text):"""
new_divider = """        if is_heading(text):"""
text = text.replace(old_divider, new_divider)

# In parse_block, check if D ends with a heading
old_ret = "    return [result]"
new_ret = """    
    # Check if last option (usually D) ends with a heading
    if result.get("options"):
        last_opt = list(result["options"].keys())[-1]
        opt_text = result["options"][last_opt]
        # Split by newlines from the end to find a heading
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
                return [result, divider]
                
    return [result]"""
text = text.replace(old_ret, new_ret)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
