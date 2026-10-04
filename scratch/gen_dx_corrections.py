import json
from pathlib import Path

data = json.loads(Path("data/testres/Integrals_v2.json").read_text(encoding="utf-8"))
corrections = {}

for q in data:
    q_text = q.get("question")
    if not q_text:
        continue
    
    if "\\int" in q_text and not q_text.strip().endswith("dx"):
        corrections[str(q["id"])] = {
            "question": q_text.strip() + " dx"
        }

Path("data/corrections/Integrals_v2.suggested.json").write_text(json.dumps(corrections, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Generated {len(corrections)} suggestions in Integrals_v2.suggested.json")
