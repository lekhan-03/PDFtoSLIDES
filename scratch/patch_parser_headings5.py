with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

old_ret = """    result["question"]      = question
    result["options"]       = options
    result["question_type"] = "mcq"
    result["parsed_ok"]     = True
    return result"""

new_ret = """    result["question"]      = question
    result["options"]       = options
    result["question_type"] = "mcq"
    result["parsed_ok"]     = True

    last_opt = list(result["options"].keys())[-1]
    opt_text = result["options"][last_opt]
    words = opt_text.split()
    from src.headings import is_heading
    for i in range(min(4, len(words) - 1), 0, -1):
        suffix = ' '.join(words[-i:]).strip()
        if is_heading(suffix) and ' '.join(words[:-i]).strip():
            result["options"][last_opt] = ' '.join(words[:-i]).strip()
            divider = {
                "question_type": "divider",
                "question": suffix,
                "id": None,
                "parsed_ok": True
            }
            return [result, divider]

    return result"""

text = text.replace(old_ret, new_ret)

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
