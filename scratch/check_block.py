import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    for opt, text in q.get('options', {}).items():
        if 'Block' in text:
            print(f"ID {q.get('id')} Option {opt}: {text}")
