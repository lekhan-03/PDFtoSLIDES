import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('data/testres/Integrals.json', encoding='utf-8'))
for q in d:
    if '2-3 sinx' in q.get('question', ''):
        print(f"ID {q['id']}: {repr(q['question'])}")
