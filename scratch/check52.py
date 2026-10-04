import json
import sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('data/outputs/chemistry_2026_10_03_130427.json', encoding='utf-8'))
for q in d:
    if '52.' in q['question']:
        print(f"ID {q['id']} raw text: {repr(q['question'])}")
        print(f"ID {q['id']} options: {q.get('options')}")
        break
