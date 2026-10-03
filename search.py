import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

for f_name in os.listdir("data/tests/testres"):
    if f_name.endswith(".json"):
        with open("data/tests/testres/" + f_name, "r", encoding="utf-8") as f:
            questions = json.load(f)
            for q in questions:
                if "$$" in q.get("question", ""):
                    print(f_name, repr(q["question"]))
