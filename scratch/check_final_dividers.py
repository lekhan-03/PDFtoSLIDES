import json
import glob
files = glob.glob('data/outputs/chemistry_*.json')
latest = max(files)
data = json.load(open(latest, encoding='utf-8'))
for i, q in enumerate(data):
    if q.get('question_type') == 'divider':
        print(f"Index {i}, id: {q.get('id')}, question: {q.get('question')}")
