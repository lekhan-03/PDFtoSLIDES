import json
data = json.load(open('data/outputs/Integrals_v3.json', encoding='utf-8'))

for q in data:
    q_text = q.get('question', '')
    if 'anti-derivative' in q_text:
        print(f"ID {q.get('id')} Option D: {q.get('options', {}).get('D')}")
    if '2025' in q_text or '2025-1' in q_text:
        print(f"ID {q.get('id')} Stem: {q_text}")
