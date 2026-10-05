import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    if q.get('id') in [55, 118, 155, 172, 194]:
        print(f"ID {q['id']} type: {q.get('question_type')} options: {list(q.get('options', {}).keys())}")
