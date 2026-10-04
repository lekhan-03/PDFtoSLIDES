import re
import os
import json

with open("stage2.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("    data = json.load(open(json_path, encoding='utf-8'))")
if idx == -1:
    print("Could not find data = json.load(...) in stage2.py!")
else:
    insertion = """
    # ── Load and apply corrections ──────────────────────────────────────────
    import os
    corrections_path = os.path.join("data", "corrections", os.path.basename(json_path))
    if os.path.exists(corrections_path):
        try:
            with open(corrections_path, 'r', encoding='utf-8') as f:
                corrections = json.load(f)
            
            applied = []
            for q in data:
                q_id = str(q['id'])
                if q_id in corrections:
                    c = corrections[q_id]
                    if 'question' in c:
                        q['question'] = c['question']
                    if 'options' in c:
                        q['options'] = c['options']
                    q['_corrected'] = True
                    applied.append(q_id)
                    
            if applied:
                print(f"applied {len(applied)} corrections: ids {', '.join(applied)}")
        except Exception as e:
            print(f"Error loading corrections: {e}")
"""
    end_of_line = text.find("\n", idx)
    text = text[:end_of_line+1] + insertion + text[end_of_line+1:]
    
    idx2 = text.find("if report.get('reasons'):")
    if idx2 != -1:
        text = text.replace("if report.get('reasons'):", 
                            "if report.get('reasons') and not q.get('_corrected'):")
        print("Patched review list logic")

    with open("stage2.py", "w", encoding="utf-8") as f:
        f.write(text)
        print("Patched stage2.py")
