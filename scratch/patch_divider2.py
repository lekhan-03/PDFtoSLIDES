import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

search_parser = """        if _looks_like_open_question(text):
            result["question"]      = text.strip()
            result["question_type"] = "open"
            result["parsed_ok"]     = True
            return result
        result["question"] = text.strip()
        return result"""

replace_parser = """        if _looks_like_open_question(text):
            result["question"]      = text.strip()
            result["question_type"] = "open"
            result["parsed_ok"]     = True
            return result
        
        words = text.strip().split()
        if len(words) <= 4 and text.strip() and text.strip()[0].isalpha():
            result["question"] = text.strip()
            result["question_type"] = "divider"
            result["id"] = None
            result["parsed_ok"] = True
            return result
            
        result["question"] = text.strip()
        return result"""

if search_parser in text:
    text = text.replace(search_parser, replace_parser)
    with open("src/parser.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Patched src/parser.py")
else:
    print("Could not find search string in src/parser.py")
