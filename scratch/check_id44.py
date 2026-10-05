import json
data = json.load(open('data/outputs/chemistry_v4.json', encoding='utf-8'))
for q in data:
    if q.get('id') == 44:
        print(f"ID 44 Option D: {q.get('options', {}).get('D')}")
print('Dividers found:')
for q in data:
    if q.get('question_type') == 'divider':
        print(f"- {q.get('question')}")
