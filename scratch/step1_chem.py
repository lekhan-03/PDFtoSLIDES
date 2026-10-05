import json
import re

data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))

for q in data:
    qid = q.get('id')
    if qid in [41, 42, 44]:
        print(f"--- ID {qid} ---")
        print(f"question: {repr(q.get('question'))}")
        print(f"options: {repr(q.get('options'))}")

caret_count = 0
spaced_formula_count = 0

def check_text(text):
    global caret_count, spaced_formula_count
    if not text: return
    if '^{' in text:
        caret_count += 1
    if re.search(r'[A-Za-z\]]\s+\d(?!\d)', text):
        spaced_formula_count += 1

for q in data:
    check_text(q.get('question'))
    for opt, txt in q.get('options', {}).items():
        check_text(txt)

print(f"Stems/options containing '^{{': {caret_count}")
print(f"Stems/options containing a spaced formula like 'Cl 2' or '[NO] 2': {spaced_formula_count}")
