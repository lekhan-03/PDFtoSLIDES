import json
data = json.load(open('data/testres/Integrals_v2.json', encoding='utf-8'))
for q in data:
    question = q.get('question', '')
    if question.startswith('The anti-derivative of'):
        print(f"ID {q['id']} (anti-derivative): D = {repr(q.get('options', {}).get('D', ''))}")
    if 'sin x-cos x' in question.replace('\u2212', '-') or 'sin x - cos x' in question.replace('\u2212', '-'):
        print(f"ID {q['id']} (e^x question): stem = {repr(question)}")
print(f'Total questions: {len(data)}')
