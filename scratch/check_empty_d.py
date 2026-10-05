import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    if q.get('options') and not q['options'].get('D'):
        print(f"ID {q.get('id')} has empty Option D")
