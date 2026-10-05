import json
import re
from pathlib import Path

data = json.load(open('data/outputs/Integrals_v2.json', encoding='utf-8'))
corrections = {}

for q in data:
    q_text = q.get("question")
    if not q_text:
        continue
    
    int_count = q_text.count('∫') + q_text.count('\\int')
    if int_count == 0:
        continue
        
    diff_count = len(re.findall(r'(?<![a-zA-Z])d[a-zA-Zθ]+', q_text))
    if diff_count > 0:
        continue
        
    # Find the math run with the integral
    math_runs = re.findall(r'\$.*?\$', q_text)
    for run in math_runs:
        if '∫' in run or '\\int' in run:
            if 'x' in run.lower() or 'X' in run:
                new_run = run[:-1].strip() + ' dx$'
            else:
                new_run = run[:-1].strip() + ' dt$'
                
            new_q_text = q_text.replace(run, new_run)
            corrections[str(q["id"])] = {
                "question": new_q_text
            }
            break

output_path = Path("data/corrections/Integrals_v2.suggested.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(corrections, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Generated {len(corrections)} suggestions in {output_path.name}")
count = 0
for k, v in corrections.items():
    if count < 3:
        print(f"ID {k}: {v['question']}")
        count += 1
    else:
        break
