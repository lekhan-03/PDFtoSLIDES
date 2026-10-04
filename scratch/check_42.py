import json
d = json.load(open('data/outputs/chemistry_2026_10_03_130427.json', encoding='utf-8'))
for q in d:
    if q['id'] in [42, 43, 44]:
        print(f"ID {q['id']} raw question: {repr(q['question'])}")
        print(f"ID {q['id']} options: {q.get('options')}")
