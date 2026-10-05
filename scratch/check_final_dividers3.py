import json
import glob
files = glob.glob('data/outputs/chemistry_*.json')
latest = max(files)
data = json.load(open(latest, encoding='utf-8'))
for i, q in enumerate(data):
    if q.get('question_type') == 'divider':
        prev_id = data[i-1].get('id') if i > 0 else None
        next_id = data[i+1].get('id') if i < len(data)-1 else None
        page = q.get('page', 'Unknown')
        print(f"Divider: '{q.get('question')}' (Page {page}) - Before ID: {prev_id}, After ID: {next_id}")
