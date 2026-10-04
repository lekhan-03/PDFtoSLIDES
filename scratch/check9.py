import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('data/tests/Integrals.json', encoding='utf-8'))
for q in d:
    if q.get('id') == 9:
        print(f"ID {q['id']}: {repr(q['question'])}")
