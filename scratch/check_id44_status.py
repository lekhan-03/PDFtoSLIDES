import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    if q.get('id') == 44:
        print(f"ID {q['id']} parsed_ok: {q.get('parsed_ok')} type: {q.get('question_type')} options: {q.get('options')}")
