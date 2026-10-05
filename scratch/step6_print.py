import json
data = json.load(open('data/outputs/Integrals_v2.json', encoding='utf-8'))
for i, q in enumerate(data):
    if q.get('question') and 'The anti-derivative of' in q.get('question') and 'sqrt' in q.get('question'):
        print(f"Option D: {q.get('options', {}).get('D')}")
        if i+1 < len(data):
            print(f"Next stem: {data[i+1].get('question')}")
        break
