import re

with open("src/parser.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix the syntax error in src/parser.py
text = text.replace("text = re.sub(r'✉.*?(\n|$)', '', text, flags=re.IGNORECASE)",
                    "text = re.sub(r'✉.*?(\\n|$)', '', text, flags=re.IGNORECASE)")

with open("src/parser.py", "w", encoding="utf-8") as f:
    f.write(text)
