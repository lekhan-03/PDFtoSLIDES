import json
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('data/testres/Integrals.json', encoding='utf-8'))
for q in d:
    if '2-3 sinx' in q.get('question', ''):
        print(f"Found in testres ID {q['id']}: {repr(q['question'])}")

baseline_path = 'tests/baseline/Integrals.json'
if os.path.exists(baseline_path):
    d2 = json.load(open(baseline_path, encoding='utf-8'))
    for q in d2:
        if q.get('id') == 9:
            print(f"Found in baseline ID {q['id']}: {repr(q['question'])}")
