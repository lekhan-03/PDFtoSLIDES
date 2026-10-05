import json
data = json.load(open('data/outputs/chemistry_2026_10_05_111433.json', encoding='utf-8'))
for i, q in enumerate(data):
    if q.get('question_type') == 'divider':
        print(f"Index {i}, question: {q.get('question')}")
