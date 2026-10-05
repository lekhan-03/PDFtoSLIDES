import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    if q.get('id') in [41, 42]:
        print(f"ID {q['id']} stem: {q.get('question')}")
