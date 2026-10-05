import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    if q.get('id') in [41, 42]:
        print(f"ID {q['id']} stem: {q.get('question')}")
count = 0
for q in data:
    if '^{' in q.get('question', ''): count += 1
    for opt in q.get('options', {}).values():
        if '^{' in opt: count += 1
print(f"Count of '^{{': {count}")
