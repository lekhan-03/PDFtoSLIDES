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
        
    # check_math logic
    dx_count = q_text.count('dx') + q_text.count('dt') + q_text.count('dy') + q_text.count('du') + q_text.count('dv') + q_text.count('dθ')
    if dx_count > 0:
        continue
        
    # Find the math run with the integral
    math_runs = re.findall(r'\$.*?\$', q_text)
    for run in math_runs:
        if '∫' in run or '\\int' in run:
            # Check if the integrand is just a number or constant
            # Everything after the integral sign until the end
            # e.g., $∫_{1}^{sqrt(3)} 3$ -> " 3$"
            after_int = re.sub(r'.*[∫\\](int)?(_\{.*?\})?(\^\{.*?\})?\s*', '', run).replace('$', '').strip()
            
            if re.match(r'^[\d\.]+$', after_int) or after_int == '':
                print(f"ID {q['id']}: {run} -> Reason: integrand probably lost (fraction)")
                break
                
            if 'x' in run.lower() or 'X' in run:
                new_run = run[:-1].strip() + ' dx$'
                suggestion = new_run
            else:
                new_run = run[:-1].strip() + ' dt$'
                suggestion = new_run
                
            new_q_text = q_text.replace(run, new_run)
            corrections[str(q["id"])] = {
                "question": new_q_text
            }
            print(f"ID {q['id']}: {run} -> Suggestion: {suggestion}")
            break

output_path = Path("data/corrections/Integrals_v2.suggested.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(corrections, indent=2, ensure_ascii=False), encoding="utf-8")
