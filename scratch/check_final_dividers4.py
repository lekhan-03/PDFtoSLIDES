import json
data = json.load(open('data/outputs/chemistry_2026_10_05_112001.json', encoding='utf-8'))
for i, q in enumerate(data):
    if q.get('question_type') == 'divider':
        prev_id = data[i-1].get('id') if i > 0 else None
        next_id = data[i+1].get('id') if i < len(data)-1 else None
        page = q.get('page', 'Unknown')
        print(f"Divider: '{q.get('question')}' (Page {page}) - Before ID: {prev_id}, After ID: {next_id}")
