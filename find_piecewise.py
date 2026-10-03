import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("data/tests/testres/Integrals.json", "r", encoding="utf-8") as f:
    questions = json.load(f)
    for q in questions:
        text = q.get("question", "")
        if "if" in text and "{" in text:
            print(f"ID {q.get('id')}: {repr(text)}")
